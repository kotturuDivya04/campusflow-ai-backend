# Migration & Reuse Report

What was taken from the original `campusflow_backend/`, what was rebuilt, what
was discarded, and every limitation the finalized schema imposed.

The original backend was **not deleted or modified**. This is a new,
self-contained folder built alongside it.

---

## 1. Executive summary

The original backend is a well-engineered **in-memory simulation engine**. It
models the appointment domain with its own vocabulary — `office_hours`,
`sessions`, `appointments`, `meetings`, `queue_entries` — keyed by UUIDs, with a
SQLAlchemy ORM (`app/persistence/orm.py`) describing that model.

The finalized schema describes a **different, narrower data model**: BIGINT
identity keys, a single `requests` table with a five-value status, an
auth-oriented `tokens` table, and no availability tables at all.

These two models are not reconcilable by renaming. So the decision was:

* **Discard** the original persistence layer entirely (its ORM describes tables
  that do not exist in the finalized schema).
* **Reuse the decision logic** — priority, ETA, transitions, clock, config,
  errors — which is genuinely valuable, framework-agnostic and well-tested.
* **Rebuild** the persistence, API and workflow layers directly against the
  finalized schema.

Net result: roughly the original's algorithmic core survives, adapted; the
storage and transport layers are new.

---

## 2. Files reused

### Reused essentially unchanged

| Original file | New location | Notes |
|---|---|---|
| `app/core/clock.py` | `app/core/clock.py` | `Clock` / `SystemClock` / `VirtualClock`. Kept verbatim in spirit — deterministic time injection is what makes the ETA testable. |

### Reused with adaptation

| Original file | New location | What changed |
|---|---|---|
| `app/providers/baseline.py` → `RuleBasedPriorityProvider` | `app/services/priority.py` | Retargeted from the original `QueueEntry` ORM object to the pure `QueueEntryView` dataclass. Weight table (`OVERRIDE` 2, `CONFIRMED` 1) and the "arrival time is not a priority term" rule kept exactly. |
| `app/providers/baseline.py` → `DeterministicETAProvider` | `app/services/eta.py` | Same formula shape; simplified to the fields the finalized schema (+ `queue_entries`) actually stores. Break handling and `max(0, …)` guards retained. |
| `app/domain/transitions.py` | `app/services/transitions.py` | Rewritten around the **five** statuses `requests.status` permits, plus a separate queue-state table. The original's richer status set could not be persisted. |
| `app/core/errors.py` | `app/core/errors.py` | Trimmed to the MVP surface; each error now carries an `http_status` so the API layer needs no lookup table. |
| `app/core/config_value.py` + `app/providers/baseline_profile.py` (`BASELINE_CONFIG`) | `app/core/config.py` + `app/services/buffer.py` | The original's `BUFFER_SIZE = 5` and default durations survive as `DEFAULT_BUFFER_MINUTES = 5` and `DEFAULT_MEETING_MINUTES = 15`, but resolution now prefers `system_settings` over app config. |
| `app/providers/interfaces.py` | `app/ai/interfaces.py` | The provider-Protocol pattern was a genuinely good idea and was kept, re-scoped to the three AI capabilities the brief asks for. |

### Discarded

| Original file | Why |
|---|---|
| `app/persistence/orm.py` | Describes `office_hours`, `sessions`, `appointments`, `meetings`, UUID keys — none of which exist in the finalized schema. Keeping it would mean maintaining a second, contradictory schema. |
| `app/persistence/repository.py`, `app/persistence/sql_store.py` | Bound to the discarded ORM. |
| `app/domain/models.py` | Domain entities keyed to the old model. Replaced by `app/services/domain.py` (pure dataclasses) and `app/models/models.py` (schema-faithful ORM). |
| `app/services/session_service.py`, `meeting_service.py`, `queue_service.py`, `recovery_service.py` | Built around `sessions` and in-memory recovery. The new `QueueService` reconstructs state from `queue_entries` on every read, which makes a dedicated recovery service unnecessary. |
| `app/services/container.py` | Manual DI container. Replaced by FastAPI's `Depends` (`app/api/deps.py`). |
| `app/services/metrics.py` | Analytics — explicitly Phase 2. |
| `app/api/main.py` | Exposed the simulation model. Replaced entirely. |
| `app/core/enums.py` | Enum values the finalized schema's CHECK constraints forbid. Replaced by `app/core/enums.py`, which encodes only permitted values plus a documented `LIFECYCLE_MAP`. |
| `scripts/init_db.py` | Created the old tables. Replaced by `app/db/init_db.py` (applies the canonical SQL) plus an Alembic scaffold. |
| `tests/test_simulations.py`, `tests/harness.py` | Test the simulation engine. Replaced by six pure test modules plus an API suite. |
| bundled Windows `venv/` | Not portable; `requirements.txt` + Dockerfile replace it. |

### New

`app/models/`, `app/schemas/`, `app/repositories/`, `app/api/`,
`app/notifications/`, `app/db/`, `app/services/free_slot_engine.py`,
`free_slot_service.py`, `appointment_service.py`, `queue_service.py`,
`queue_logic.py`, `token_service.py`, `timetable_importer.py`,
`app/ai/deterministic.py`, both migrations, the Alembic scaffold, Docker files
and all documentation.

---

## 3. Old model → new model mapping

| Original concept | Finalized-schema equivalent |
|---|---|
| `office_hours` (recurring availability) | **No equivalent, and none added.** Out of MVP scope by instruction: any free academic slot is bookable, and faculty control access via approve / reject / reschedule / mark-busy. |
| `sessions` (a dated instance of an office hour) | Implicit: `(faculty_id, meeting_date, academic_slot_id)` on `queue_entries`. |
| `appointments` | `requests` (with `request_type = 'Appointment'`). |
| `appointment.status` (rich enum) | Split: committed states → `requests.status` (5 permitted values); operational states → `queue_entries.state`. See §5. |
| `meetings` (actual start/finish) | `queue_entries.started_at` / `completed_at`. |
| `queue_entries` (in-memory) | `queue_entries` (persisted, additive table). |
| `token` (queue ticket) | Split: canonical `tokens` row with `token_type='REQUEST_ACCESS'` for access, plus `queue_entries.token_number` for the position. |
| UUID primary keys | BIGINT identity keys throughout. |
| `provider` interfaces | `app/ai/interfaces.py`. |

---

## 4. Logic retained / removed / postponed

**Retained:** deterministic priority ordering and its tiebreak rules; the ETA
formula and its non-negativity guarantees; explicit transition tables with
`IllegalTransition`; injectable clock; buffer as configuration rather than a
constant; the ORM-free decision core so it stays unit-testable.

**Hardened during verification (see VERIFICATION_REPORT.md):** `mark_busy` made
idempotent (get-or-create on the busy block); a working reschedule→reapproval
path (a withdrawn queue entry is revived in place, respecting
`UNIQUE(request_id)`); token exchange rewritten to swap token numbers through a
sentinel so it never trips the token-number unique constraint mid-transaction;
and a notifications mark-as-read capability added on the existing
`notifications.is_read` column.

**Removed:** the whole simulation harness and virtual-time driver; in-memory
session recovery; the metrics/analytics module; the manual DI container; the old
ORM and its repositories.

**Postponed (Phase 2, per the brief):** recurring office hours and advanced
availability windows; AI-driven priority; behavioural prediction of no-shows;
advanced automatic rescheduling; analytics dashboards; external ERP/LMS
integration; multi-step approval chains.

The architecture keeps room for all of these: priority and ETA sit behind small
pure functions, the AI layer is already a Protocol boundary, and the additive
tables carry the timestamps that any future analytics would need.

---

## 5. Schema limitations encountered

Each of these is a real constraint of the finalized schema, documented rather
than silently worked around.

1. **`requests.status` allows only five values.** `Pending, Approved, Rejected,
   Cancelled, Rescheduled`. There is no `Busy`, `CheckedIn`, `InProgress`,
   `Completed` or `NoShow`. → Committed states go in `requests.status`;
   operational states go in `queue_entries.state`; `LIFECYCLE_MAP` in
   `app/core/enums.py` documents every mapping in one place.

2. **`requests` has no slot or date column** — only `scheduled_time TIMESTAMPTZ`.
   → The requested `(date, slot)` is encoded as
   `combine(date, slot.start_time)` and recovered by matching the time back to
   `academic_slots` (start times are unique in the seeded data). After approval
   the authoritative pair lives on `queue_entries`.

3. **`requests` has no rejection-reason column.** → The reason is delivered to
   the student via `notifications.message` but is not queryable as a field.

4. **`tokens` is an auth table, not a queue ticket.** Its `token_type` CHECK is
   `API_KEY / PASSWORD_RESET / EMAIL_VERIFICATION / REQUEST_ACCESS` and it has
   no position, check-in, delay or priority columns. → A genuine
   `REQUEST_ACCESS` row is still created on approval (using the schema as
   intended); the queue position lives on `queue_entries.token_number`.

5. **No availability or busy-block table exists.** → `faculty_busy_blocks`
   (additive). Writing busy blocks into `timetable` would corrupt the academic
   timetable, which the schema treats as recurring truth.

6. **`academic_slots` has no `type` column and no lunch row.** Lunch is the
   *gap* between Period 4 (ends 12:20) and Period 5 (starts 13:30). → The engine
   never sees a lunch candidate; a name-pattern guard is retained for other
   datasets.

7. **`events` belongs to clubs, not faculty.** `events.club_id` exists;
   there is no `events.faculty_id`, and `venue_bookings` links classrooms and
   users rather than faculty availability. → Event-conflict exclusion is
   implemented in the engine but has no data source, so it is marked 🟡 partial.
   One column (`events.faculty_id`) would complete it.

8. **`notifications.type` allows only four values.** → Twelve business events
   are mapped onto those four, with detail carried in title/message.

9. **No table for a two-party token-exchange agreement.** → The MVP applies an
   exchange immediately, with both parties notified. A consent workflow would
   need an approvals row.

10. **`system_settings` shipped no scheduling rows.** → Migration 002 inserts
    `APPOINTMENT_BUFFER_MINUTES`, `DEFAULT_MEETING_MINUTES`, `QUEUE_BREAK_AFTER`
    and `QUEUE_BREAK_MINUTES` with `ON CONFLICT DO NOTHING`, so an existing
    deployment's values are never overwritten.

---

## 6. MVP assumptions

* **Approval and confirmation are one step.** Approving a request confirms it
  and issues the token. A separate CONFIRMED stage would need another status
  value the schema does not permit.
* **Capacity is one appointment per `(faculty, date, slot)`.**
* **Pending requests do not occupy a slot.** Several students may hold pending
  requests for the same slot; the faculty approves at most one.
* **Faculty user id == faculty id.** The schema defines `faculty.id` as a FK to
  `users.id`, so notifications address the faculty by the same id. The same
  holds for `students.id`.
* **Timestamps are timezone-aware UTC** throughout.
* **The current term** is read from `system_settings.CURRENT_ACADEMIC_YEAR` and
  `CURRENT_SEMESTER` (both already seeded) when matching timetable rows.
* **Check-in gates being called, not priority rank.**

---

## 7. Recommendations for Phase 2

1. **Add `events.faculty_id`** (or a `faculty_events` join table). This is the
   single smallest change that upgrades event-conflict exclusion from partial to
   complete — the engine code already supports it.
2. **Add `requests.academic_slot_id` and `requests.meeting_date`.** This would
   remove the timestamp-encoding workaround and make dated-slot queries direct
   and indexable.
3. **Add `requests.rejection_reason`** so the reason is queryable rather than
   living only in a notification.
4. **Widen `notifications.type`**, or add a `notifications.event_key` column, so
   clients can filter by business event rather than parsing titles.
5. **Consider folding `queue_entries` into the canonical schema.** It has proven
   necessary; adopting it officially removes the "additive table" caveat.
6. **Write to `audit_logs`** on approve / reject / busy / settings changes — the
   table exists and is currently unused.
7. **Use `ai_logs` and `chat_history`** when the LLM-backed implementations of
   the three AI Protocols are introduced.
8. **Add a consent step for token exchange** using the existing `approvals`
   table.
