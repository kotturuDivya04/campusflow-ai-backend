"""
Integration tests for the Admin API extension:

    POST /admin/students
    POST /admin/faculty
    GET  /admin/appointments
    GET  /admin/notifications

REQUIREMENTS are the same as tests/test_api.py: fastapi, httpx, sqlalchemy,
psycopg2 and a PostgreSQL seeded with migrations 001 + 002 + 003. The whole
module is skipped automatically when those are unavailable (tests/conftest.py).

Two deliberate choices:

  * Tokens are minted with the application's own `create_access_token` rather
    than by POSTing to /auth/login, and the acting users are looked up BY ROLE
    from the seeded database rather than hard-coded. This keeps the tests
    independent of which fixture accounts a given seed happens to contain and
    of their passwords, while still exercising the real
    get_current_user/require_admin dependency chain.
  * Every account these tests create is removed again in fixture teardown, so
    the suite leaves no permanent rows behind. Deleting the users row cascades
    to students/faculty/user_roles (ON DELETE CASCADE in the schema).
"""
from __future__ import annotations

import datetime as _dt
import unittest
import uuid

try:
    import pytest
except ImportError:  # plain `unittest discover` in a minimal environment
    raise unittest.SkipTest("pytest is not installed; skipping API integration tests")

from tests.conftest import requires_web_stack

pytestmark = requires_web_stack


# --- fixtures ---------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def db():
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        yield session


def _user_id_with_role(db, role_name: str) -> int:
    from sqlalchemy import select

    from app.models import Role, UserRole

    uid = db.scalar(
        select(UserRole.user_id).join(Role, Role.id == UserRole.role_id)
        .where(Role.name == role_name).order_by(UserRole.user_id).limit(1))
    if uid is None:
        pytest.skip(f"no seeded user holds the {role_name} role")
    return uid


def _headers(user_id: int, roles: list[str]) -> dict:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=roles)}"}


@pytest.fixture(scope="module")
def admin_headers(db):
    return _headers(_user_id_with_role(db, "SuperAdmin"), ["SuperAdmin"])


@pytest.fixture(scope="module")
def student_headers(db):
    return _headers(_user_id_with_role(db, "Student"), ["Student"])


@pytest.fixture(scope="module")
def department_id(db):
    from sqlalchemy import select

    from app.models import Department

    dept = db.scalar(select(Department.id).order_by(Department.id).limit(1))
    if dept is None:
        pytest.skip("no departments seeded")
    return dept


@pytest.fixture
def suffix(db):
    """A unique suffix per test, with teardown that removes anything created."""
    from sqlalchemy import text

    token = uuid.uuid4().hex[:10]
    yield token
    db.rollback()
    db.execute(text("DELETE FROM users WHERE username LIKE :p"), {"p": f"%{token}"})
    db.commit()


def _student_payload(suffix: str, department_id: int, **overrides) -> dict:
    payload = {
        "username": f"t_stu_{suffix}",
        "email": f"t_stu_{suffix}@example.edu",
        "password": "TestPassword123",
        "first_name": "Test",
        "last_name": "Student",
        "phone": None,
        "roll_number": f"T_ROLL_{suffix}",
        "department_id": department_id,
        "section_id": None,
        "admission_year": 2025,
        "current_semester": 1,
    }
    payload.update(overrides)
    return payload


def _faculty_payload(suffix: str, department_id: int, **overrides) -> dict:
    payload = {
        "username": f"t_fac_{suffix}",
        "email": f"t_fac_{suffix}@example.edu",
        "password": "TestPassword123",
        "first_name": "Test",
        "last_name": "Faculty",
        "phone": None,
        "faculty_code": f"T_FAC_{suffix}",
        "department_id": department_id,
        "designation": "Assistant Professor",
        "office_location": None,
    }
    payload.update(overrides)
    return payload


# --- OpenAPI surface --------------------------------------------------------
def test_admin_endpoints_are_exposed(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/admin/students"]
    assert "post" in paths["/admin/faculty"]
    assert "get" in paths["/admin/appointments"]
    assert "get" in paths["/admin/notifications"]


def test_admin_read_endpoints_are_read_only(client):
    """No mutation verbs were added to the appointment/notification views."""
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths["/admin/appointments"]) == {"get"}
    assert set(paths["/admin/notifications"]) == {"get"}


# --- authorization ----------------------------------------------------------
@pytest.mark.parametrize("method,path", [
    ("post", "/admin/students"),
    ("post", "/admin/faculty"),
    ("get", "/admin/appointments"),
    ("get", "/admin/notifications"),
])
def test_requires_authentication(client, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401


@pytest.mark.parametrize("method,path", [
    ("post", "/admin/students"),
    ("post", "/admin/faculty"),
    ("get", "/admin/appointments"),
    ("get", "/admin/notifications"),
])
def test_student_is_forbidden(client, student_headers, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    resp = getattr(client, method)(path, headers=student_headers, **kwargs)
    assert resp.status_code == 403


# --- POST /admin/students ---------------------------------------------------
def test_create_student_writes_existing_tables(client, db, admin_headers,
                                               department_id, suffix):
    from app.models import Student, User

    payload = _student_payload(suffix, department_id)
    resp = client.post("/admin/students", headers=admin_headers, json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["roll_number"] == payload["roll_number"]
    assert body["email"] == payload["email"]

    db.expire_all()
    user = db.get(User, body["id"])
    student = db.get(Student, body["id"])
    assert user is not None and student is not None
    # students.id IS users.id — the schema's shared-primary-key subtype.
    assert student.id == user.id
    assert user.password_hash != payload["password"]


def test_create_student_assigns_the_existing_student_role(
        client, db, admin_headers, department_id, suffix):
    from app.repositories.repositories import UserRepository

    resp = client.post("/admin/students", headers=admin_headers,
                       json=_student_payload(suffix, department_id))
    assert resp.status_code == 201, resp.text
    db.expire_all()
    assert UserRepository(db).roles_for(resp.json()["id"]) == ["Student"]


def test_created_student_can_authenticate(client, admin_headers,
                                          department_id, suffix):
    """The password is hashed with the project's existing hasher, so the new
    account works against the existing /auth/login path."""
    payload = _student_payload(suffix, department_id)
    assert client.post("/admin/students", headers=admin_headers,
                       json=payload).status_code == 201

    resp = client.post("/auth/login", json={"username": payload["username"],
                                            "password": payload["password"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["roles"] == ["Student"]


def test_duplicate_username_conflicts(client, admin_headers, department_id, suffix):
    payload = _student_payload(suffix, department_id)
    assert client.post("/admin/students", headers=admin_headers,
                       json=payload).status_code == 201
    dup = dict(payload, email=f"other_{suffix}@example.edu",
               roll_number=f"OTHER_{suffix}")
    assert client.post("/admin/students", headers=admin_headers,
                       json=dup).status_code == 409


def test_duplicate_roll_number_conflicts(client, admin_headers, department_id, suffix):
    payload = _student_payload(suffix, department_id)
    assert client.post("/admin/students", headers=admin_headers,
                       json=payload).status_code == 201
    dup = dict(payload, username=f"other_{suffix}", email=f"other_{suffix}@example.edu")
    assert client.post("/admin/students", headers=admin_headers,
                       json=dup).status_code == 409


def test_unknown_department_leaves_no_partial_user(client, db, admin_headers, suffix):
    """Atomicity: a failure after the users insert must roll the user back."""
    from sqlalchemy import select

    from app.models import User

    payload = _student_payload(suffix, 10**9)
    assert client.post("/admin/students", headers=admin_headers,
                       json=payload).status_code == 404

    db.rollback()
    assert db.scalar(select(User).where(User.username == payload["username"])) is None


def test_unknown_section_leaves_no_partial_user(client, db, admin_headers,
                                                department_id, suffix):
    from sqlalchemy import select

    from app.models import User

    payload = _student_payload(suffix, department_id, section_id=10**9)
    assert client.post("/admin/students", headers=admin_headers,
                       json=payload).status_code == 404

    db.rollback()
    assert db.scalar(select(User).where(User.username == payload["username"])) is None


def test_invalid_semester_is_rejected(client, admin_headers, department_id, suffix):
    payload = _student_payload(suffix, department_id, current_semester=99)
    assert client.post("/admin/students", headers=admin_headers,
                       json=payload).status_code == 422


# --- POST /admin/faculty ----------------------------------------------------
def test_create_faculty_writes_existing_tables(client, db, admin_headers,
                                               department_id, suffix):
    from app.models import Faculty, User

    payload = _faculty_payload(suffix, department_id)
    resp = client.post("/admin/faculty", headers=admin_headers, json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["faculty_code"] == payload["faculty_code"]

    db.expire_all()
    user = db.get(User, body["id"])
    fac = db.get(Faculty, body["id"])
    assert user is not None and fac is not None
    assert fac.id == user.id
    assert user.password_hash != payload["password"]


def test_create_faculty_assigns_the_existing_faculty_role(
        client, db, admin_headers, department_id, suffix):
    from app.repositories.repositories import UserRepository

    resp = client.post("/admin/faculty", headers=admin_headers,
                       json=_faculty_payload(suffix, department_id))
    assert resp.status_code == 201, resp.text
    db.expire_all()
    assert UserRepository(db).roles_for(resp.json()["id"]) == ["Faculty"]


def test_duplicate_faculty_code_conflicts(client, admin_headers, department_id, suffix):
    payload = _faculty_payload(suffix, department_id)
    assert client.post("/admin/faculty", headers=admin_headers,
                       json=payload).status_code == 201
    dup = dict(payload, username=f"other_{suffix}", email=f"other_{suffix}@example.edu")
    assert client.post("/admin/faculty", headers=admin_headers,
                       json=dup).status_code == 409


# --- GET /admin/appointments ------------------------------------------------
def test_appointments_expose_existing_request_fields(client, admin_headers):
    resp = client.get("/admin/appointments", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    if not rows:
        pytest.skip("no requests present in this database")
    row = rows[0]
    for field in ("id", "student_id", "faculty_id", "request_type", "title",
                  "description", "status", "student_name", "faculty_name"):
        assert field in row
    # There is no `purpose` column in the schema and none was invented.
    assert "purpose" not in row


def test_appointments_status_filter(client, admin_headers):
    resp = client.get("/admin/appointments?status=Pending", headers=admin_headers)
    assert resp.status_code == 200
    assert all(r["status"] == "Pending" for r in resp.json())


def test_appointments_reject_unknown_status(client, admin_headers):
    assert client.get("/admin/appointments?status=Nonsense",
                      headers=admin_headers).status_code == 422


def test_appointments_reject_inverted_date_range(client, admin_headers):
    resp = client.get("/admin/appointments?date_from=2030-01-02&date_to=2030-01-01",
                      headers=admin_headers)
    assert resp.status_code == 422


def test_appointments_limit_and_offset(client, admin_headers):
    all_rows = client.get("/admin/appointments", headers=admin_headers).json()
    if len(all_rows) < 2:
        pytest.skip("needs at least two requests to test paging")
    first = client.get("/admin/appointments?limit=1", headers=admin_headers).json()
    second = client.get("/admin/appointments?limit=1&offset=1", headers=admin_headers).json()
    assert len(first) == 1 and len(second) == 1
    assert first[0]["id"] != second[0]["id"]


def test_appointments_student_filter_is_scoped(client, admin_headers):
    rows = client.get("/admin/appointments", headers=admin_headers).json()
    if not rows:
        pytest.skip("no requests present in this database")
    target = rows[0]["student_id"]
    filtered = client.get(f"/admin/appointments?student_id={target}",
                          headers=admin_headers).json()
    assert filtered and all(r["student_id"] == target for r in filtered)


def test_appointments_issue_a_single_query(client, admin_headers):
    """The joined repository query must not degrade into per-row lookups."""
    from sqlalchemy import event

    from app.db.session import engine

    seen = []

    def _count(conn, cursor, statement, params, context, executemany):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        assert client.get("/admin/appointments", headers=admin_headers).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert len(seen) <= 2, f"expected one SELECT, saw {len(seen)}"


# --- GET /admin/notifications -----------------------------------------------
def test_notifications_are_readable_system_wide(client, admin_headers):
    resp = client.get("/admin/notifications", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    if not rows:
        pytest.skip("no notifications present in this database")
    assert {"id", "user_id", "title", "message", "type", "is_read"} <= set(rows[0])


def test_notifications_type_filter(client, admin_headers):
    resp = client.get("/admin/notifications?type=SYSTEM", headers=admin_headers)
    assert resp.status_code == 200
    assert all(r["type"] == "SYSTEM" for r in resp.json())


def test_notifications_reject_unknown_type(client, admin_headers):
    assert client.get("/admin/notifications?type=NOT_A_TYPE",
                      headers=admin_headers).status_code == 422


def test_notifications_user_filter(client, admin_headers):
    rows = client.get("/admin/notifications", headers=admin_headers).json()
    if not rows:
        pytest.skip("no notifications present in this database")
    target = rows[0]["user_id"]
    filtered = client.get(f"/admin/notifications?user_id={target}",
                          headers=admin_headers).json()
    assert filtered and all(r["user_id"] == target for r in filtered)


def test_notifications_is_read_filter(client, admin_headers):
    resp = client.get("/admin/notifications?is_read=false", headers=admin_headers)
    assert resp.status_code == 200
    assert all(r["is_read"] is False for r in resp.json())
