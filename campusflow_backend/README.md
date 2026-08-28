# CampusFlow AI — MVP Backend

A FastAPI + PostgreSQL backend for student–faculty appointment scheduling with a
live token queue, built **directly on the finalized database schema**.

The schema in `migrations/001_core_schema.sql` is a verbatim copy of the team's
canonical `database/docker-entrypoint-initdb.d/schema.sql` and was **not edited**.
Exactly two strictly-additive tables were introduced in a separate migration
(`002_mvp_operational.sql`) for features the canonical schema has no home for;
both are justified in `SCHEMA_CAPABILITY_MAP.md`.

---

## 1. Quick start

### Docker (recommended)

```bash
cd campusflow_mvp_backend
cp .env.example .env
docker compose up --build
```

* API: <http://localhost:8000>
* Interactive docs: <http://localhost:8000/docs>
* Database: `localhost:5433` (deliberately not 5432, so it never clashes with
  the original stack's container)

The database container applies `migrations/001` → `002` → `003_seed.sql` in
filename order on first start.

### Local Python

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # point CAMPUSFLOW_DATABASE_URL at your DB
python -m app.db.init_db --seed      # applies 001 + 002 (+ seed)
uvicorn app.main:app --reload
```

An Alembic scaffold is also provided for teams that already run the finalized
schema and want a versioned upgrade instead:

```bash
alembic upgrade head                 # creates ONLY the two additive tables
```

---

## 2. Architecture

```
app/
  api/          routers (thin) + dependencies (auth, RBAC, service wiring)
  services/     ALL business rules
  repositories/ ALL database queries
  models/       SQLAlchemy 2.0 ORM, mirroring the finalized schema
  schemas/      Pydantic v2 request/response contracts (separate from ORM)
  notifications/ DB-backed notifications + email stub
  ai/           AI boundary: Protocols + deterministic implementations
  core/         config, enums, errors, security, clock
  db/           engine, session, init_db
```

Layering rule: **routers → services → repositories → ORM.** A router never
writes a query; a service never touches an HTTP object.

The decision core — Free Slot Engine, priority, ETA, transitions, queue
reconstruction, timetable parsing — imports **nothing** from SQLAlchemy or
FastAPI. That is why it can be unit-tested with the standard library alone
(see §7).

---

## 3. The Free Slot Engine

```
Available Slot =
    Academic Slot
  − Teaching Classes
  − Lunch / Break Slots
  − Approved Appointment Conflicts
  − Event Conflicts
  − Buffer Conflicts
  − Dated Busy Blocks
```

`app/services/free_slot_engine.py` implements this as a pure function;
`app/services/free_slot_service.py` resolves the inputs from the database.

Endpoint:

```
GET /faculty/{faculty_id}/free-slots?date=YYYY-MM-DD
```

Results are always returned in chronological order.

### Documented behaviour

| Topic | Behaviour |
|---|---|
| **Capacity** | 1 appointment per `(faculty, date, academic_slot)`. |
| **Pending requests** | Do **not** occupy a slot. Two students may hold pending requests on the same slot; the faculty approves at most one. |
| **Lunch / breaks** | The seeded `academic_slots` contain no lunch row — lunch is the *gap* between Period 4 (ends 12:20) and Period 5 (starts 13:30), so it can never be booked. For robustness with other datasets the engine also drops any slot whose name matches `lunch / break / recess / interval / tea`. |
| **Event conflicts** | **Partial.** The canonical `events` table belongs to clubs, not faculty, so faculty-level event exclusion is only applied when the caller supplies event slot ids. With the seeded data this set is empty. See `SCHEMA_CAPABILITY_MAP.md`. |
| **Buffer** | Every occupied interval is expanded by the buffer on both sides; a candidate slot intersecting an expanded window is dropped. |
| **Recurring office hours** | Intentionally **not implemented** (out of MVP scope). Any valid free academic slot is bookable; faculty retain control through approve / reject / reschedule / mark-busy. |

### Buffer configuration

The buffer is never hard-coded. Resolution order:

1. `system_settings.APPOINTMENT_BUFFER_MINUTES` (canonical table — wins)
2. `Settings.DEFAULT_BUFFER_MINUTES` in `app/core/config.py` (default **5**)

`app/services/buffer.py` is the single reader, used by slot computation, booking
validation, rescheduling and ETA alike. The same pattern covers
`DEFAULT_MEETING_MINUTES`, `QUEUE_BREAK_AFTER` and `QUEUE_BREAK_MINUTES`.

---

## 4. Appointment lifecycle

The canonical `requests.status` CHECK constraint allows exactly five values:
`Pending, Approved, Rejected, Cancelled, Rescheduled`. The brief's richer
lifecycle is therefore split across two layers, with no invented enum values:

| Brief status | Stored as |
|---|---|
| PENDING / APPROVED / REJECTED / CANCELLED | `requests.status` |
| CONFIRMED | `requests.status = 'Approved'` — approval and confirmation are a **single step** in this MVP |
| RESCHEDULE_REQUIRED | `requests.status = 'Rescheduled'` |
| BUSY | a `faculty_busy_blocks` row; affected requests move to `Rescheduled` and their queue entries to `WITHDRAWN` |
| CHECKED_IN / IN_PROGRESS / COMPLETED / NO_SHOW | `queue_entries.state` |

Illegal transitions raise `409 Conflict` (`app/services/transitions.py`).

**Storing the requested date + slot.** `requests` has no `academic_slot_id` and
no date column — only `scheduled_time TIMESTAMPTZ`. A request's requested slot is
therefore encoded as `datetime.combine(date, slot.start_time)` and recovered by
matching the time back to the `academic_slots` row (start times are unique).
Once approved, the authoritative `(date, slot)` lives on the `queue_entries` row.

---

## 5. Live queue, tokens and ETA

Queue state is **always reconstructed from `queue_entries` rows** — never from
process memory — so restarts and multiple workers stay consistent.

Two different things are called a "token":

* **Access token** — a real row in the canonical `tokens` table with
  `token_type = 'REQUEST_ACCESS'`, created on approval.
* **Queue token number** — the student's position integer, on
  `queue_entries.token_number` (the schema has no column for it).

Priority is deterministic and explainable (`OVERRIDE` > `CONFIRMED`, ties broken
by booking timestamp then id). **Arrival time is not a priority term** — check-in
gates *eligibility to be called*, not rank. No AI influences priority.

### ETA formula

For a waiting student *S*, with `ahead` = the students called before *S*:

```
remaining_current = max(0, (started_at + default_meeting) − now)   # if a meeting is IN_PROGRESS, else 0
ahead_time        = Σ (effective_minutes[a] + buffer)  for a in ahead
recorded_delays   = Σ delay_minutes[a]  for a in ahead  + delay of the current meeting
breaks            = (break_after > 0) ? (len(ahead) // break_after) × break_minutes : 0

ETA(S) = max(0, remaining_current + ahead_time + recorded_delays + breaks)
```

Inputs: actual meeting start time, recorded delays, default meeting duration,
buffer, and the number of active tokens ahead. `max(0, …)` is applied at every
stage, so the ETA can never be negative. It is deterministic, not predictive AI
— by design for the MVP.

---

## 6. API reference

All endpoints except `/health` and `/auth/login` require
`Authorization: Bearer <jwt>`.

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login` | returns JWT + roles |
| GET | `/auth/me` | current user and roles |

### Faculty (role: `Faculty`)
| Method | Path | Notes |
|---|---|---|
| GET | `/faculty/me` | profile |
| GET | `/faculty/me/timetable` | own timetable |
| GET | `/faculty/{faculty_id}/free-slots?date=` | free slot engine (any authenticated user) |
| GET | `/faculty/me/requests/pending` | pending requests |
| POST | `/faculty/requests/{id}/approve` | approve → access token + queue entry |
| POST | `/faculty/requests/{id}/reject` | body: `{reason}` |
| POST | `/faculty/requests/{id}/reschedule` | body: `{academic_slot_id, date, note?}` |
| POST | `/faculty/me/busy` | body: `{academic_slot_id, date, reason?}` |
| GET | `/faculty/me/queue?date=` | live queue grouped by slot |
| POST | `/faculty/queue/{entry_id}/begin` | records actual start time |
| POST | `/faculty/queue/{entry_id}/complete` | records actual finish time |
| POST | `/faculty/queue/{entry_id}/no-show` | |
| GET | `/faculty/me/schedule-summary?date=` | deterministic AI summary |

### Student (role: `Student`)
| Method | Path | Notes |
|---|---|---|
| GET | `/student/me` | profile |
| GET | `/student/faculty?q=` | search faculty |
| POST | `/student/appointments` | submit request (validates + rejects duplicates) |
| GET | `/student/appointments` | request history |
| POST | `/student/appointments/{id}/cancel` | |
| GET | `/student/tokens` | own queue tokens |
| GET | `/student/tokens/{entry_id}` | token + position + ETA |
| POST | `/student/tokens/{entry_id}/check-in` | |
| POST | `/student/tokens/{entry_id}/delay` | body: `{minutes}` |
| POST | `/student/tokens/{entry_id}/exchange` | body: `{other_queue_entry_id}` |
| GET | `/student/notifications` | |
| POST | `/student/notifications/{id}/read` | mark one notification read (ownership-checked) |
| POST | `/student/notifications/read-all` | mark all of the caller's notifications read |
| GET | `/student/faculty/{id}/recommended-slots?date=` | deterministic AI recommendation |

### Admin (roles: `SuperAdmin`, `DepartmentAdmin`)
| Method | Path | Notes |
|---|---|---|
| GET / POST | `/admin/slots` | manage academic slots |
| GET | `/admin/timetable/{faculty_id}` | timetable records |
| POST | `/admin/timetable/upload` | CSV or JSON import |
| GET | `/admin/users` | users with roles |
| GET | `/admin/settings` | system settings |
| PUT | `/admin/settings/{key}` | update a setting (e.g. the buffer) |

### Error codes
`400` validation · `401` unauthenticated · `403` wrong role / not your record ·
`404` not found · `409` duplicate, slot unavailable, illegal transition ·
`422` invalid payload.

---

## 7. Tests

The suite has three tiers, split by what each needs:

**1. Pure tests — no dependencies at all:**

```bash
python -m unittest discover -s tests
```

63 tests covering the Free Slot Engine (teaching / break / approved / busy /
event exclusion, buffer behaviour, ordering), priority ordering, the ETA
formula, request and queue transitions, live-queue reconstruction, token
exchange rules, timetable parsing and the deterministic AI layer.

**2. Database integration tests — need only SQLAlchemy (SQLite, no server):**

```bash
pip install -r requirements.txt          # or just SQLAlchemy
python -m unittest tests.test_integration_db -v
```

11 tests that drive the real ORM, repositories and services against a live
SQLAlchemy engine (SQLite, foreign keys enforced) with genuine transactions and
constraint enforcement: approval → token + queue entry, double-approve
blocking, capacity, duplicate-token rejection, the full meeting lifecycle with
actual timestamps, ETA, Mark Busy reconciliation + idempotency, reschedule →
reapproval, and token-exchange authorization/swap/guards. They auto-skip if
SQLAlchemy is absent. These were used to harden the backend during verification
(see `VERIFICATION_REPORT.md`).

**3. API integration tests — need the full web stack and a running database:**

```bash
pip install -r requirements.txt
python -m app.db.init_db --seed
pytest tests/test_api.py -v
```

They skip automatically when FastAPI/httpx are absent.

Running `python -m unittest discover -s tests` with SQLAlchemy installed executes
tiers 1 + 2 (74 tests) and skips tier 3; in a bare environment it runs tier 1
and skips the rest.

---

## 8. Notifications

The canonical `notifications.type` CHECK allows only four values. The MVP keeps
an application-level event catalogue (`app/notifications/service.py`) mapping
each business event — request submitted, approved, rejected, busy, rescheduled,
token generated, queue update, meeting approaching, delay recorded, token
exchange, meeting started/completed — onto one of those four types, with the
detail carried in the title and message. Email delivery sits behind `EmailStub`
so a real provider can be added without touching callers.

## 9. AI boundary

`app/ai/interfaces.py` defines three Protocols — `SlotRecommender`,
`ConflictExplainer`, `ScheduleSummarizer` — that accept and return plain data.
`app/ai/deterministic.py` ships rule-based implementations used today. The AI
surface is advisory only: it never influences priority or approval decisions.
Swapping in an LLM-backed implementation means writing a class that satisfies
the same Protocol; no scheduling code changes.

## 10. Further reading

* `SCHEMA_CAPABILITY_MAP.md` — every capability mapped to tables, services and
  endpoints, marked complete / partial / deferred.
* `MIGRATION_AND_REUSE_REPORT.md` — what was reused from the original backend,
  what was discarded and why, and every schema limitation encountered.
* `IMPLEMENTATION_NOTES.md` — assumptions, trade-offs and Phase 2 recommendations.
