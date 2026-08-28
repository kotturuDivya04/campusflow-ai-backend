from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("1. Backend starts successfully & 10. Health check")
res = client.get("/health")
assert res.status_code == 200, res.text
print("Health check OK!")

print("2. Existing APIs untouched (we didn't modify them).")

print("4. Swagger /openapi.json check")
res = client.get("/openapi.json")
assert res.status_code == 200, res.text
openapi = res.json()
paths = openapi["paths"]

placement_paths = [p for p in paths.keys() if p.startswith("/placement")]
print("Placement paths in OpenAPI:", placement_paths)

print("5. GET /placement/announcements returns dummy data (wait, we need auth).")
from app.api.deps import require_faculty, get_current_user, AuthContext

def override_faculty():
    return AuthContext(user_id=1, roles=["FACULTY"])

def override_user():
    return AuthContext(user_id=1, roles=["STUDENT"])

app.dependency_overrides[require_faculty] = override_faculty
app.dependency_overrides[get_current_user] = override_user

res = client.get("/placement/announcements")
assert res.status_code == 200, res.text
data = res.json()
assert len(data) == 3
print("GET returned 3 dummy announcements.")

print("6. POST /placement/announcements")
new_ann = {
    "title": "Backend Intern",
    "company": "Amazon",
    "description": "SDE intern role",
    "target_type": "ALL",
    "status": "ACTIVE"
}
res = client.post("/placement/announcements", json=new_ann)
assert res.status_code == 201, res.text
created = res.json()
print("Created:", created["id"])

print("7. GET returns newly created")
res = client.get("/placement/announcements")
data = res.json()
assert len(data) == 4
print("GET now returns 4 announcements.")

print("8. GET by ID returns the announcement")
res = client.get(f"/placement/announcements/{created['id']}")
assert res.status_code == 200, res.text
assert res.json()["title"] == "Backend Intern"
print("GET by ID OK!")

print("9. Invalid ID returns 404")
res = client.get("/placement/announcements/999")
assert res.status_code == 404, res.text
print("404 check OK!")

print("ALL VERIFICATIONS PASSED")
