# Verification Report

This report records exactly what was executed, what was **not**, the results,
and every bug fixed during hardening. Nothing is claimed as passing unless it
was actually run.

---

## 1. Environment used

| | |
|---|---|
| OS / Python | Ubuntu 24.04 container, CPython 3.12.3 |
| Network egress | **Blocked** — proxy returns `host_not_allowed` for `pypi.org`, `files.pythonhosted.org`, Debian/Ubuntu mirrors. `pip install` cannot reach any index. |
| Docker | **Not installed** (`docker: not found`) |
| PostgreSQL | **Not available** (no `postgres`/`psql`/`initdb`/`pg_ctl`; no server) |
| Preinstalled Python pkgs | `PyJWT 2.7.0` only (plus stdlib `sqlite3`, `yaml`) |
| SQLAlchemy | `2.0.51` — **usable**: vendored from the original project's bundled venv, run in pure-Python mode (its optional C extension is a Windows binary and is skipped) |
| FastAPI / pydantic / psycopg2 / passlib / pytest / httpx | **Unavailable.** `pydantic-core` and `psycopg2` are compiled binaries (Windows `.pyd`) that cannot load on this Linux/CPython-3.12 host. |

**Consequence.** The requested "install `requirements.txt`, start PostgreSQL via
Docker, run the API suite against PostgreSQL" could **not** be executed here.
Instead, the data + service layers were verified against a **real SQLAlchemy
engine on SQLite** (foreign keys enforced), which exercises the ORM,
repositories, services, transactions and DB constraints for real. The
FastAPI/pydantic HTTP layer was verified by compilation and import analysis
only. Every item below states which applies.

---

## 2. Commands executed

```bash
# 2.1 Confirm environment limits
pip3 install --break-system-packages --dry-run fastapi     # No matching distribution (network blocked)
python3 -c "import urllib.request; urllib.request.urlopen('https://pypi.org/simple/')"
                                                            # HTTP 403 x-deny-reason: host_not_allowed
which docker psql postgres initdb                           # all absent

# 2.2 Vendor SQLAlchemy (pure-python) from the original project's bundled venv
cp -r campusflow_backend/venv/Lib/site-packages/sqlalchemy /home/claude/vendor/
find /home/claude/vendor/sqlalchemy -name '*.pyd' -delete   # drop Windows C-ext -> pure-python fallback
PYTHONPATH=/home/claude/vendor python3 -c "import sqlalchemy; print(sqlalchemy.__version__)"  # 2.0.51

# 2.3 Whole-tree byte-compile
find . -name '*.py' -not -path '*/__pycache__/*' | xargs python3 -m py_compile   # ALL COMPILE OK

# 2.4 Pure unit suite (zero third-party deps)
python3 -m unittest discover -s tests

# 2.5 Real-database integration harness (ORM + repositories + services on SQLite)
PYTHONPATH=/home/claude/vendor:. CAMPUSFLOW_DATABASE_URL="sqlite:////tmp/cf.db" \
    python3 verify_harness.py

# 2.6 Startup import matrix (which modules import; exact failure reasons)
PYTHONPATH=/home/claude/vendor:. CAMPUSFLOW_DATABASE_URL="sqlite:////tmp/cf.db" \
    python3 -c "import app.main"     # fails only: ModuleNotFoundError: fastapi

# 2.7 Schema integrity
diff migrations/001_core_schema.sql database/docker-entrypoint-initdb.d/schema.sql
md5sum migrations/001_core_schema.sql database/.../schema.sql
```

The harness builds the schema from the ORM metadata (a SQLite-only shim renders
`BigInteger` PKs as `INTEGER` so SQLite autoincrements them; production uses the
canonical `GENERATED AS IDENTITY` SQL), seeds a minimal dataset, then drives the
**actual** repositories and services.

---

## 3. Migration results

| Step | Result |
|---|---|
| Apply `001_core_schema.sql` to PostgreSQL | **Not executed** — no PostgreSQL here. |
| Apply `002_mvp_operational.sql` | **Not executed** on PostgreSQL. Equivalent tables (from the matching ORM models) were created and exercised on SQLite. |
| Apply `003_seed.sql` | **Not executed** on PostgreSQL. A minimal ORM-built seed was used in the harness. |
| `001` == canonical `schema.sql` | **Verified — byte-for-byte identical** (`md5 e1812524cd94ada750b0271c245185e8` on both). |
| Additive tables isolated in one migration | **Verified** — only `002_mvp_operational.sql` contains `faculty_busy_blocks` and `queue_entries`; `001` is unmodified canonical. |
| ORM matches additive DDL | **Verified by inspection** — the SQL additionally enforces `CHECK (delay_minutes >= 0)` at the DB level (a superset of the ORM). |

> **Not claimed:** that the hand-written `001/002/003` SQL runs cleanly on a real
> PostgreSQL server. The team must run `README.md` §1 on a networked host with
> Docker. What *is* verified: the ORM the app queries through matches those
> tables and works against a live SQL engine.

---

## 4. Startup result

`import app.main` / `uvicorn app.main:app` — **Not executed to a running
server**; FastAPI and pydantic-core are unavailable here. Precise matrix:

```
OK    app.core.{config,enums,errors,security}
OK    app.db.{base,session}, app.models, app.repositories.repositories
OK    app.services.{appointment_service,queue_service,free_slot_service,timetable_importer}
OK    app.notifications.service, app.ai.{deterministic,interfaces}
FAIL  app.schemas    -> ModuleNotFoundError: pydantic
FAIL  app.api.deps   -> ModuleNotFoundError: fastapi
FAIL  app.main       -> ModuleNotFoundError: fastapi
```

Every failure is a **missing third-party package**, not a code defect: 15 of 18
core modules import cleanly and the whole tree byte-compiles. The three failures
resolve once `requirements.txt` is installed on a networked host.

---

## 5. Test results

### 5.1 Pure unit suite — EXECUTED

`python3 -m unittest discover -s tests` -> `Ran 64 tests — OK (skipped=1)`

| Outcome | Count |
|---|---|
| **Passed** | **63** |
| Failed | 0 |
| Errored | 0 |
| Skipped | 1 (`tests/test_api.py`, auto-skips without FastAPI/httpx) |

Per module: free_slot_engine 9 · priority_eta 9 · transitions 10 · queue 15 ·
importer 11 · ai 9.

### 5.2 Real-database integration harness — EXECUTED (SQLite, FK-enforced)

`verify_harness.py` -> `RESULT: 34 passed, 0 failed`

Covered (all passed): free-slot exclusion of teaching + named breaks + ordering;
submit -> pending + faculty notification; duplicate-submit rejection; approve ->
REQUEST_ACCESS token + queue entry (committed & persisted); **double-approve
blocked (no duplicate token/queue)**; faculty.id/student.id shared-PK
correspondence; capacity=1; **DB rejection of duplicate (faculty,date,slot,
token#)**; check-in -> begin -> complete with actual timestamps;
illegal-transition rejection; ETA computed & non-negative; **mark-busy
withdrawal + reschedule of affected requests + idempotency**; **reschedule ->
reapproval producing a valid WAITING entry on the new slot**; **token exchange
ownership/authorization, number swap, both-way linkage, blocked once a meeting
is in progress**; notification mark-as-read + mark-all-read.

### 5.3 API layer (`tests/test_api.py`) — NOT EXECUTED

Requires FastAPI TestClient + pydantic + a live database, none available here.
The file is complete and runs on a networked host after
`pip install -r requirements.txt` and `python -m app.db.init_db --seed`.
**No API-through-HTTP result is claimed.**

---

## 6. Bugs fixed

All found by the real-DB harness; all were on the review checklist.

1. **`mark_busy` was not idempotent.** A second Mark Busy on the same
   `(faculty, date, slot)` raised `IntegrityError` on `uq_faculty_busy` (an
   unhandled 500). *Fix:* `BusyRepository.get_or_create` + `mark_busy` reuses an
   existing block; reconciliation is idempotent (withdrawn entries aren't
   re-selected; rescheduled requests are no longer Pending). Verified: repeat
   call -> single block, no crash.

2. **Reschedule -> reapproval crashed.** Rescheduling withdraws the queue entry
   but keeps the row; reapproval then tried to INSERT a second entry for the
   same request, violating `uq_queue_request`. There was **no working reapproval
   path**. *Fix:* `QueueRepository.revive` resets the existing (withdrawn) row to
   WAITING on the new slot with a fresh token + access token; `approve` reuses
   it. A guard rejects re-approval when an *active* entry already exists.

3. **Token exchange crashed.** The naive two-row token-number swap momentarily
   left two rows sharing a number, violating
   `uq_queue_token (faculty,date,slot,token_number)`. *Fix:* swap via a negative
   sentinel (real numbers >= 1) with a flush between steps, so the DB never sees
   a duplicate. Verified: numbers swap; `exchanged_with_id` set both ways.

4. **Missing notifications mark-as-read.** `notifications.is_read` existed but
   nothing set it. *Added:* `POST /student/notifications/{id}/read`
   (ownership-checked) and `POST /student/notifications/read-all`, plus
   repository methods. Verified against the real DB.

Non-code items confirmed while hardening: services/repositories **never commit**
(routers own the transaction — verified by grep); every mutating route commits;
event-conflict exclusion is now explicitly **deferred** in code and docs.

---

## 7. Remaining limitations

1. **PostgreSQL not exercised here.** All DB verification used SQLite. SQLite and
   PostgreSQL differ in identity columns, type affinity and true concurrency.
   The team must run `README.md` §1 on a networked host to confirm the
   `001/002/003` SQL and the API tests against real PostgreSQL. This is the most
   important follow-up.
2. **FastAPI app not started.** Import/startup and the HTTP test suite depend on
   FastAPI + pydantic-core, unavailable here; verified only by compilation and
   import analysis.
3. **Concurrency proven only at the constraint level.** True simultaneous
   approvals can't be simulated on SQLite. Safety rests on `uq_queue_token` + the
   single approval transaction; under high contention a `SELECT ... FOR UPDATE`
   on the faculty row is the recommended PostgreSQL hardening.
4. **`scheduled_time` slot encoding remains.** Still fragile if two slots ever
   share a start time (see §8 / `PROPOSED_requests_slot_columns.sql.txt`).
5. **Rejection reason and per-event notification type** are carried in the
   notification message, not dedicated columns (schema has no field).
6. **Event-conflict exclusion is deferred**, not partial: the schema has no
   faculty->event relationship (`events.organizing_club_id` links clubs only).

---

## 8. Schema additions requiring team approval

Two additive tables **already proposed and used** (isolated in
`002_mvp_operational.sql`; canonical `schema.sql` untouched):

* **`faculty_busy_blocks`** — dated, slot-scoped faculty unavailability. No
  canonical table can hold it (not student-scoped; `requests.status` has no
  `Busy`; `timetable` is recurring truth).
* **`queue_entries`** — the live-queue lifecycle (position, check-in, actual
  start/finish, delay, priority, exchange). The canonical **`tokens` table
  cannot serve as the live queue token table**: it is an auth table whose
  `token_type` CHECK is `API_KEY / PASSWORD_RESET / EMAIL_VERIFICATION /
  REQUEST_ACCESS`, with no columns for queue position, check-in, meeting
  timestamps, delay, priority or exchange. A genuine `REQUEST_ACCESS` row is
  still created on approval; the queue position lives on
  `queue_entries.token_number`.

One change **proposed for review, deliberately not applied**
(`migrations/PROPOSED_requests_slot_columns.sql.txt` — the `.sql.txt` extension
means neither `init_db.py` nor the Postgres init container can auto-run it):

* **`requests.academic_slot_id` + `requests.meeting_date`** (both nullable,
  additive, backfillable) — the **smallest safe** change that removes the fragile
  `scheduled_time` -> slot reconstruction. Blast radius: two columns, one model,
  one service method. It alters a canonical table, so it is left for team
  approval rather than applied silently.

Recommended next (team-owned): add **`events.faculty_id`** to complete
event-conflict exclusion with no engine change.
