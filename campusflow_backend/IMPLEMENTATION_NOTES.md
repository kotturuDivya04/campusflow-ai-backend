# Implementation Notes

Design decisions, trade-offs, and an honest account of what was and was not
executed during development.

---

## 1. Why the decision core is ORM-free

Every scheduling rule — free slots, priority, ETA, transitions, queue
reconstruction, timetable parsing — is a pure function over plain dataclasses in
`app/services/`. Repositories translate ORM rows into those dataclasses.

Two benefits:

* **Testability.** 63 unit tests run with `python -m unittest discover -s tests`
  and *no installed dependencies at all* — no database, no FastAPI, no pytest.
* **Correctness under review.** A judge or reviewer can read
  `free_slot_engine.py` end to end and verify it against the brief's formula
  without tracing a query.

The cost is one extra projection step in each repository, which is cheap and
explicit.

## 2. Verification performed — and its limits

**Honest statement of what was actually executed.**

The development container had **no network access**, so `fastapi`, `sqlalchemy`,
`pydantic`, `alembic`, `passlib` and `pytest` could not be installed. That
shaped what could be proven:

| Check | Status |
|---|---|
| Pure unit tests (`python -m unittest discover -s tests`) | ✅ **Executed — 63 passed, 1 skipped** |
| `py_compile` across the entire tree (ORM, schemas, routers, main, Alembic) | ✅ **Executed — all files compile** |
| FastAPI app import / startup | ❌ **Not executed** — FastAPI is not installed |
| SQLAlchemy model registration against a live engine | ❌ **Not executed** |
| API integration tests (`tests/test_api.py`) | ❌ **Not executed** — they skip automatically without the web stack |
| Migrations applied to a real PostgreSQL | ❌ **Not executed** — no database available |

So: **the scheduling logic is verified by execution; the API, ORM and migration
layers are verified only by syntax check and careful review against the
finalized schema.** They are written to be correct but have not been run. First
steps on a machine with network access should be:

```bash
pip install -r requirements.txt
python -c "import app.main"          # import / startup check
python -m app.db.init_db --seed      # apply migrations
pytest tests/ -v                     # full suite including API tests
```

## 3. Trade-offs taken

**Two additive tables instead of contorting the schema.** The alternative —
encoding busy blocks as fake `requests` rows, or queue state in a JSON blob in
`system_settings` — would have kept the table count identical while making the
data meaningless. Two clean, foreign-keyed, documented tables in a *separate*
migration seemed the more honest engineering choice, and it leaves the canonical
`schema.sql` byte-for-byte untouched.

**Encoding the requested slot in `scheduled_time`.** This is the least
comfortable compromise in the build. It works because slot start times are
unique, but it is fragile if two slots ever share a start time. The Phase 2
recommendation to add `requests.academic_slot_id` would remove it entirely.

**Single-step approval.** The brief lists CONFIRMED as a distinct status; the
schema has no room for it. Rather than invent a sixth status or add a column,
approval and confirmation were merged and the merge documented everywhere it
matters.

**Buffer as an interval expansion, not a per-appointment field.** The buffer
widens each occupied interval symmetrically. This is simple, symmetric and easy
to reason about; it does mean a slot adjacent to a class is dropped when the
buffer exceeds the gap, which is the intended protective behaviour.

**Notification richness in the message, not the type.** Twelve business events
map onto four permitted `type` values. Clients that need to branch on the exact
event currently cannot do so cleanly — hence the Phase 2 suggestion of an
`event_key` column.

## 4. Concurrency

Approval checks slot availability inside the same transaction that creates the
queue entry, and `queue_entries` carries
`UNIQUE (faculty_id, meeting_date, academic_slot_id, token_number)` plus
`UNIQUE (request_id)`. Two simultaneous approvals for the same slot will
therefore collide at the database rather than both succeeding. Under heavy
contention a `SELECT … FOR UPDATE` on the faculty row would be the next
refinement; it was judged unnecessary for MVP load.

## 5. What was deliberately not built

Per the brief's explicit scope boundaries: recurring office hours or availability
windows; AI-influenced priority or approval; no-show prediction; automatic
rescheduling beyond the manual reschedule endpoint; analytics dashboards;
external ERP/LMS integration; multi-level approval chains; PDF/Excel timetable
parsing (the original `parser/` project already covers that and can feed the
CSV/JSON import endpoint).

This is an MVP for a competition, not an ERP. The architecture leaves seams for
each of the above without carrying their weight today.

## 6. File map

```
campusflow_mvp_backend/
├── README.md                       setup, API reference, ETA formula, capacity rules
├── SCHEMA_CAPABILITY_MAP.md        capability → table → service → endpoint → status
├── MIGRATION_AND_REUSE_REPORT.md   reuse, discards, schema limitations, Phase 2
├── IMPLEMENTATION_NOTES.md         this file
├── requirements.txt / .env.example / Dockerfile / docker-compose.yml
├── alembic.ini, alembic/           versioned path for the additive tables
├── migrations/
│   ├── 001_core_schema.sql         FINALIZED schema, verbatim, unedited
│   ├── 002_mvp_operational.sql     the two additive tables + settings rows
│   └── 003_seed.sql                canonical seed data
├── app/
│   ├── main.py                     FastAPI app, error handlers, /health
│   ├── api/                        deps.py + routes/{auth,faculty,student,admin}.py
│   ├── services/                   all business rules (pure core + repo-backed services)
│   ├── repositories/               all database queries
│   ├── models/                     SQLAlchemy 2.0, mirrors the finalized schema
│   ├── schemas/                    Pydantic v2 contracts
│   ├── notifications/              event catalogue + email stub
│   ├── ai/                         Protocols + deterministic implementations
│   ├── core/                       config, enums, errors, security, clock
│   └── db/                         base, session, init_db
└── tests/
    ├── test_free_slot_engine.py    ┐
    ├── test_priority_eta.py        │
    ├── test_transitions.py         ├─ pure: run with zero dependencies
    ├── test_queue.py               │
    ├── test_importer.py            │
    ├── test_ai.py                  ┘
    ├── test_api.py                 needs fastapi + httpx + a live database
    └── conftest.py
```
