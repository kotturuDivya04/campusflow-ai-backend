# Schema Capability Map

Every MVP capability, mapped to the tables and columns that store it, the
service that implements it, the endpoint that exposes it, and an honest status.

**Legend** — ✅ complete · 🟡 partial · ⏸ deferred (Phase 2)

---

## 1. Authentication & roles

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| Login with username + password | `users.username`, `users.password_hash`, `users.status` | `core/security.verify_password` | `POST /auth/login` | ✅ |
| JWT issue / decode | *(stateless; not persisted)* | `core/security.create_access_token` | `POST /auth/login` | ✅ |
| Role-based authorization | `roles.name`, `user_roles` | `api/deps.AuthContext.require` | all protected routes | ✅ |
| Current user introspection | `users`, `user_roles`, `roles` | `repositories.UserRepository` | `GET /auth/me` | ✅ |
| Password reset / email verification | `tokens.token_type` supports both | — | — | ⏸ |

## 2. Profiles & directory

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| Faculty profile | `faculty` + `users` | `FacultyRepository` | `GET /faculty/me` | ✅ |
| Student profile | `students` + `users` | `StudentRepository` | `GET /student/me` | ✅ |
| Faculty search | `faculty.faculty_code`, `users.first_name/last_name` | `FacultyRepository.search` | `GET /student/faculty?q=` | ✅ |

## 3. Timetable

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| Academic slot definitions | `academic_slots` | `SlotRepository` | `GET/POST /admin/slots` | ✅ |
| Timetable records | `timetable` (all columns) | `TimetableRepository` | `GET /faculty/me/timetable`, `GET /admin/timetable/{faculty_id}` | ✅ |
| CSV / JSON timetable import | `timetable` | `timetable_importer` (parsing pure, persistence separate) | `POST /admin/timetable/upload` | ✅ |
| Duplicate-safe import | `uq_timetable_faculty/section/classroom` | `TimetableRepository.exists` | same | ✅ |
| PDF / Excel timetable import | — | *(original `parser/` project covers this)* | — | ⏸ |

## 4. Free Slot Engine

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| Enumerate academic slots for a date | `academic_slots` | `FreeSlotService` | `GET /faculty/{id}/free-slots` | ✅ |
| Exclude teaching classes | `timetable.faculty_id/day_of_week/academic_slot_id/academic_year/semester` | `TimetableRepository.teaching_slot_ids` | same | ✅ |
| Exclude lunch / break | *(no row exists — lunch is the 12:20–13:30 **gap**)* + name-pattern guard | `free_slot_engine` | same | ✅ |
| Exclude approved appointments | `queue_entries.meeting_date/academic_slot_id/state` | `RequestRepository.approved_slot_ids_on_date` | same | ✅ |
| Exclude faculty busy blocks | `faculty_busy_blocks` *(additive)* | `BusyRepository.busy_slot_ids` | same | ✅ |
| Apply buffer | `system_settings.APPOINTMENT_BUFFER_MINUTES` | `buffer.BufferPolicy` + `free_slot_engine` | same | ✅ |
| Exclude event conflicts | `events` links only to **clubs** (`events.organizing_club_id`); `venue_bookings` links classrooms/users. **No faculty-to-event relationship exists in the schema.** | `free_slot_service` passes an empty event set with a documented note; engine retains the hook | same | ⏸ |
| Recurring office hours / availability windows | *(no table; out of scope by instruction)* | — | — | ⏸ |

> **Event conflicts are DEFERRED, not partial.** Because the schema exposes no
> way to associate an event with a faculty member, excluding event slots cannot
> be done correctly. The engine keeps the `event_slot_ids` parameter, so adding
> `events.faculty_id` (or a `faculty_events` join) later enables the feature with
> no engine change.

## 5. Appointment lifecycle

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| Submit request | `requests.student_id/faculty_id/request_type/title/description/status/scheduled_time` | `AppointmentService.submit` | `POST /student/appointments` | ✅ |
| Requested date + slot | `requests.scheduled_time` **only** — encoded as `combine(date, slot.start_time)` | `AppointmentService._resolve_dated_slot` | — | 🟡 |
| Duplicate rejection | `requests` + `queue_entries` | `AppointmentService.submit` | same | ✅ |
| Approve (= CONFIRMED, single step) | `requests.status='Approved'` | `AppointmentService.approve` | `POST /faculty/requests/{id}/approve` | ✅ |
| Reject with reason | `requests.status='Rejected'`; reason delivered via `notifications.message` | `AppointmentService.reject` | `POST /faculty/requests/{id}/reject` | 🟡 |
| Reschedule | `requests.status='Rescheduled'` + new `scheduled_time` | `AppointmentService.reschedule` | `POST /faculty/requests/{id}/reschedule` | ✅ |
| Reschedule → reapproval → replacement queue entry | `queue_entries` (revived in place under `UNIQUE(request_id)`) | `AppointmentService.approve` + `QueueRepository.revive` | `POST /faculty/requests/{id}/approve` | ✅ |
| Mark busy + reconcile (idempotent) | `faculty_busy_blocks` *(additive)*, `requests.status`, `queue_entries.state` | `AppointmentService.mark_busy` + `BusyRepository.get_or_create` | `POST /faculty/me/busy` | ✅ |
| Student cancel | `requests.status='Cancelled'` | `AppointmentService.cancel` | `POST /student/appointments/{id}/cancel` | ✅ |
| Illegal transition guard | — | `services/transitions` | all of the above (409) | ✅ |
| Rejection reason as a stored field | *(no `requests.rejection_reason` column)* | — | — | 🟡 |

> **Two honest limitations here.** (1) The requested slot must be reconstructed
> from a timestamp because `requests` has no `academic_slot_id`. (2) A rejection
> reason is delivered to the student in a notification but is not stored as a
> queryable column on the request, because no such column exists.

## 6. Live queue & tokens

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| Access token on approval | `tokens.token_value/token_type='REQUEST_ACCESS'/expires_at` **(canonical)** | `TokenService` | `POST /faculty/requests/{id}/approve` | ✅ |
| Queue token number | `queue_entries.token_number` *(additive — canonical `tokens` cannot hold a queue position)* | `QueueRepository.next_token_number` | same | ✅ |
| Live queue reconstruction | `queue_entries.*` (read from DB, never memory) | `queue_logic.build_snapshot` | `GET /faculty/me/queue` | ✅ |
| Check-in | `queue_entries.state`, `checked_in_at` | `QueueService.check_in` | `POST /student/tokens/{id}/check-in` | ✅ |
| Report delay | `queue_entries.delay_minutes` | `QueueService.report_delay` | `POST /student/tokens/{id}/delay` | ✅ |
| Token exchange | `queue_entries.token_number`, `exchanged_with_id` (sentinel swap avoids transient UNIQUE violation) | `QueueService.exchange` + `queue_logic.can_exchange` | `POST /student/tokens/{id}/exchange` | ✅ |
| Begin meeting (actual start) | `queue_entries.started_at`, `state='IN_PROGRESS'` | `QueueService.begin_meeting` | `POST /faculty/queue/{id}/begin` | ✅ |
| Complete meeting (actual finish) | `queue_entries.completed_at`, `state='COMPLETED'` | `QueueService.complete_meeting` | `POST /faculty/queue/{id}/complete` | ✅ |
| No-show | `queue_entries.state='NO_SHOW'` | `QueueService.mark_no_show` | `POST /faculty/queue/{id}/no-show` | ✅ |
| Deterministic priority | `queue_entries.priority_class`, `priority_score` | `services/priority` | ordering everywhere | ✅ |
| ETA | derived from `queue_entries` + `system_settings` | `services/eta` | `GET /student/tokens/{id}` | ✅ |
| Two-party consent on exchange | *(no approval table for it)* — the MVP applies it immediately | — | — | 🟡 |

## 7. Notifications

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| In-app notifications | `notifications.user_id/title/message/type/is_read` | `NotificationService` | `GET /student/notifications` | ✅ |
| 12 business events | mapped onto the 4 permitted `type` values | `notifications.EVENTS` | — | ✅ |
| Distinct event type per event | `notifications.type` CHECK allows only 4 values | — | — | 🟡 |
| Email delivery | — | `EmailStub` (interface in place) | — | ⏸ |
| Mark as read | `notifications.is_read` | `NotificationRepository.mark_read` / `mark_all_read` | `POST /student/notifications/{id}/read`, `POST /student/notifications/read-all` | ✅ |

## 8. Administration

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| Manage academic slots | `academic_slots` | `SlotRepository` | `GET/POST /admin/slots` | ✅ |
| View users and roles | `users`, `user_roles`, `roles` | `UserRepository` | `GET /admin/users` | ✅ |
| Manage system settings | `system_settings.setting_key/setting_value` | `SettingsRepository` | `GET /admin/settings`, `PUT /admin/settings/{key}` | ✅ |
| Buffer configuration | `system_settings.APPOINTMENT_BUFFER_MINUTES` | `BufferPolicy` | `PUT /admin/settings/APPOINTMENT_BUFFER_MINUTES` | ✅ |
| Audit trail of admin changes | `audit_logs` exists in the schema | — | — | ⏸ |

## 9. AI boundary

| Capability | Table(s) / column(s) | Service | Endpoint | Status |
|---|---|---|---|---|
| Slot recommendation interface | *(stateless)* | `ai/interfaces.SlotRecommender` + deterministic impl | `GET /student/faculty/{id}/recommended-slots` | ✅ |
| Conflict explanation interface | *(stateless)* | `ai/interfaces.ConflictExplainer` | used by services | ✅ |
| Schedule summary interface | *(stateless)* | `ai/interfaces.ScheduleSummarizer` | `GET /faculty/me/schedule-summary` | ✅ |
| LLM-backed implementations | `ai_logs`, `chat_history` exist for it | — | — | ⏸ |
| AI-driven priority | — | *(explicitly excluded from the MVP)* | — | ⏸ |

---

## 10. Additive tables — justification

Only two tables were added, in `migrations/002_mvp_operational.sql`. The
canonical `schema.sql` was **not modified**.

### `faculty_busy_blocks`

*Why it was unavoidable:* "faculty marks a slot busy" is a **dated, slot-scoped
availability block**. `requests` cannot hold it (a busy block belongs to no
student and `status` has no `Busy` value); `timetable` cannot hold it (that is
recurring academic scheduling, and writing to it would corrupt the timetable);
`system_settings` is key/value. Without this table, Busy could only be
approximated by mutating unrelated rows.

### `queue_entries`

*Why it was unavoidable:* the canonical `tokens` table is an **auth** table —
its `token_type` CHECK is `API_KEY / PASSWORD_RESET / EMAIL_VERIFICATION /
REQUEST_ACCESS` and it has no columns for a queue position, check-in time,
actual meeting start/finish, delay, priority or exchange. `requests.status`
permits five committed states and cannot express `CHECKED_IN`, `IN_PROGRESS`,
`COMPLETED` or `NO_SHOW`. The entire live-queue feature set — a required MVP
deliverable — has no schema home without it.

Both tables are strictly additive: they only reference canonical tables by
foreign key and no canonical table was altered, so an existing deployment can
adopt this backend with a single `alembic upgrade head`.
