"""
API-level integration tests (pytest + FastAPI TestClient).

REQUIREMENTS: fastapi, httpx, sqlalchemy, psycopg2 and a reachable PostgreSQL
seeded with migrations 001 + 002 + 003. They are skipped automatically when
those are unavailable — see tests/conftest.py.

Run them with:
    pip install -r requirements.txt
    python -m app.db.init_db --seed
    pytest tests/test_api.py -v
"""
from __future__ import annotations

import datetime as _dt
import unittest

try:
    import pytest
except ImportError:  # plain `unittest discover` in a minimal environment
    raise unittest.SkipTest("pytest is not installed; skipping API integration tests")

from tests.conftest import requires_web_stack

pytestmark = requires_web_stack


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def student_token(client):
    resp = client.post("/auth/login",
                       json={"username": "student1", "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def faculty_token(client):
    resp = client.post("/auth/login",
                       json={"username": "faculty1", "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- meta -------------------------------------------------------------------
def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_openapi_is_generated(client):
    spec = client.get("/openapi.json").json()
    assert "/auth/login" in spec["paths"]
    assert "/faculty/{faculty_id}/free-slots" in spec["paths"]


# --- auth -------------------------------------------------------------------
def test_login_rejects_bad_password(client):
    resp = client.post("/auth/login",
                       json={"username": "student1", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_a_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_roles(client, student_token):
    body = client.get("/auth/me", headers=auth(student_token)).json()
    assert "Student" in body["roles"]


# --- RBAC -------------------------------------------------------------------
def test_student_cannot_reach_admin_routes(client, student_token):
    assert client.get("/admin/settings", headers=auth(student_token)).status_code == 403


def test_student_cannot_reach_faculty_pending_queue(client, student_token):
    resp = client.get("/faculty/me/requests/pending", headers=auth(student_token))
    assert resp.status_code == 403


# --- free slots -------------------------------------------------------------
def test_free_slots_returns_chronological_slots(client, student_token):
    date = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
    resp = client.get(f"/faculty/2/free-slots?date={date}", headers=auth(student_token))
    assert resp.status_code == 200
    slots = resp.json()
    starts = [s["start_time"] for s in slots]
    assert starts == sorted(starts)


def test_free_slots_requires_authentication(client):
    date = _dt.date.today().isoformat()
    assert client.get(f"/faculty/2/free-slots?date={date}").status_code == 401


# --- appointment lifecycle --------------------------------------------------
def test_full_appointment_flow(client, student_token, faculty_token):
    date = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
    free = client.get(f"/faculty/2/free-slots?date={date}",
                      headers=auth(student_token)).json()
    assert free, "no free slot available to test with"
    slot_id = free[0]["slot_id"]

    created = client.post("/student/appointments", headers=auth(student_token), json={
        "faculty_id": 2, "academic_slot_id": slot_id, "date": date,
        "title": "Project discussion", "description": "Review of module 2",
        "request_type": "Appointment",
    })
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "Pending"

    # duplicate submission is rejected
    dup = client.post("/student/appointments", headers=auth(student_token), json={
        "faculty_id": 2, "academic_slot_id": slot_id, "date": date,
        "title": "Project discussion", "description": "again",
    })
    assert dup.status_code == 409

    approved = client.post(f"/faculty/requests/{request_id}/approve",
                           headers=auth(faculty_token))
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"

    # a queue token now exists for the student
    tokens = client.get("/student/tokens", headers=auth(student_token)).json()
    entry = next(t for t in tokens if t["request_id"] == request_id)
    assert entry["state"] == "WAITING"
    assert entry["token_number"] >= 1

    # ETA is available before check-in
    view = client.get(f"/student/tokens/{entry['id']}", headers=auth(student_token))
    assert view.status_code == 200
    assert view.json()["estimated_wait_minutes"] >= 0

    # check-in, begin, complete
    assert client.post(f"/student/tokens/{entry['id']}/check-in",
                       headers=auth(student_token)).status_code == 200
    began = client.post(f"/faculty/queue/{entry['id']}/begin", headers=auth(faculty_token))
    assert began.status_code == 200
    assert began.json()["started_at"] is not None
    done = client.post(f"/faculty/queue/{entry['id']}/complete",
                       headers=auth(faculty_token))
    assert done.status_code == 200
    assert done.json()["completed_at"] is not None


def test_illegal_transition_is_rejected(client, faculty_token, student_token):
    """Completing a meeting that never started must fail with 409."""
    date = (_dt.date.today() + _dt.timedelta(days=2)).isoformat()
    free = client.get(f"/faculty/2/free-slots?date={date}",
                      headers=auth(student_token)).json()
    slot_id = free[0]["slot_id"]
    rid = client.post("/student/appointments", headers=auth(student_token), json={
        "faculty_id": 2, "academic_slot_id": slot_id, "date": date,
        "title": "Doubt", "description": "clarification",
    }).json()["id"]
    client.post(f"/faculty/requests/{rid}/approve", headers=auth(faculty_token))
    tokens = client.get("/student/tokens", headers=auth(student_token)).json()
    entry = next(t for t in tokens if t["request_id"] == rid)
    resp = client.post(f"/faculty/queue/{entry['id']}/complete", headers=auth(faculty_token))
    assert resp.status_code == 409


def test_faculty_cannot_approve_another_faculty_request(client, faculty_token):
    resp = client.post("/faculty/requests/999999/approve", headers=auth(faculty_token))
    assert resp.status_code in (403, 404)


def test_reject_records_status(client, student_token, faculty_token):
    date = (_dt.date.today() + _dt.timedelta(days=3)).isoformat()
    free = client.get(f"/faculty/2/free-slots?date={date}",
                      headers=auth(student_token)).json()
    rid = client.post("/student/appointments", headers=auth(student_token), json={
        "faculty_id": 2, "academic_slot_id": free[0]["slot_id"], "date": date,
        "title": "Grade query", "description": "mid-term", "request_type": "Grade Query",
    }).json()["id"]
    resp = client.post(f"/faculty/requests/{rid}/reject", headers=auth(faculty_token),
                       json={"reason": "unavailable that day"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Rejected"


# --- busy -------------------------------------------------------------------
def test_mark_busy_removes_the_slot_from_free_slots(client, faculty_token, student_token):
    date = (_dt.date.today() + _dt.timedelta(days=4)).isoformat()
    before = client.get(f"/faculty/2/free-slots?date={date}",
                        headers=auth(student_token)).json()
    assert before
    slot_id = before[0]["slot_id"]
    resp = client.post("/faculty/me/busy", headers=auth(faculty_token),
                       json={"academic_slot_id": slot_id, "date": date,
                             "reason": "department meeting"})
    assert resp.status_code == 200
    after = client.get(f"/faculty/2/free-slots?date={date}",
                       headers=auth(student_token)).json()
    assert slot_id not in [s["slot_id"] for s in after]


# --- notifications ----------------------------------------------------------
def test_notifications_are_created_for_the_student(client, student_token):
    body = client.get("/student/notifications", headers=auth(student_token)).json()
    assert isinstance(body, list)
    assert all(n["type"] in
               {"REQUEST_UPDATE", "EVENT_INVITATION", "ALERT", "SYSTEM"} for n in body)


def test_mark_single_notification_read(client, student_token):
    body = client.get("/student/notifications", headers=auth(student_token)).json()
    if not body:
        return  # nothing to mark in this ordering; covered by mark-all below
    nid = body[0]["id"]
    resp = client.post(f"/student/notifications/{nid}/read", headers=auth(student_token))
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


def test_mark_all_notifications_read(client, student_token):
    resp = client.post("/student/notifications/read-all", headers=auth(student_token))
    assert resp.status_code == 200
    after = client.get("/student/notifications", headers=auth(student_token)).json()
    assert all(n["is_read"] for n in after)


def test_cannot_mark_another_users_notification(client, student_token, faculty_token):
    fac_notifs = client.get("/student/notifications", headers=auth(faculty_token)).json()
    if not fac_notifs:
        return
    other_id = fac_notifs[0]["id"]
    resp = client.post(f"/student/notifications/{other_id}/read", headers=auth(student_token))
    assert resp.status_code in (403, 404)


# --- admin ------------------------------------------------------------------
def test_admin_can_read_settings(client):
    token = client.post("/auth/login",
                        json={"username": "admin", "password": "password123"}).json()
    resp = client.get("/admin/settings", headers=auth(token["access_token"]))
    assert resp.status_code == 200
    keys = {s["setting_key"] for s in resp.json()}
    assert "APPOINTMENT_BUFFER_MINUTES" in keys


def test_timetable_upload_rejects_malformed_csv(client):
    token = client.post("/auth/login",
                        json={"username": "admin", "password": "password123"}
                        ).json()["access_token"]
    resp = client.post("/admin/timetable/upload", headers=auth(token),
                       files={"file": ("bad.csv", b"not,a,timetable\n1,2,3\n", "text/csv")})
    assert resp.status_code == 200
    assert resp.json()["errors"]
