-- ==========================================================
-- CAMPUSFLOW AI — MVP OPERATIONAL ADDITIONS (migration 002)
-- ==========================================================
-- The canonical schema (001_core_schema.sql) is the single source of truth
-- for every capability it already expresses. It does NOT, however, contain any
-- structure for the live-queue / token / check-in / delay / ETA / busy-block
-- features that the MVP brief lists as REQUIRED (brief items 9-16).
--
-- The `tokens` table in the canonical schema is an AUTH token store
-- (token_type IN 'API_KEY','PASSWORD_RESET','EMAIL_VERIFICATION','REQUEST_ACCESS')
-- and its CHECK constraint forbids reusing it as a queue-ticket table. The
-- `requests` table only carries status IN ('Pending','Approved','Rejected',
-- 'Cancelled','Rescheduled') and a single scheduled_time — it cannot hold the
-- operational sub-states (checked-in, in-progress, completed, no-show), the
-- queue position/priority, actual start/finish timestamps, or delay records.
--
-- Per the brief's primary rule, these are the ONLY additions, they are strictly
-- additive (no canonical table is renamed or altered), and every one is tied to
-- a required MVP feature. See SCHEMA_CAPABILITY_MAP.md for the full rationale.
-- ==========================================================

-- ----------------------------------------------------------
-- faculty_busy_blocks  —  "mark a dated slot Busy" (brief item 9, workflow 6/10)
-- The canonical schema has no 'Busy' request status and no dated availability
-- table. A busy block is a (faculty, date, academic_slot) tuple that removes a
-- single dated slot from the free-slot output without touching the recurring
-- timetable. This keeps a configurable availability layer addable later.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS faculty_busy_blocks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    faculty_id BIGINT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    block_date DATE NOT NULL,
    academic_slot_id BIGINT NOT NULL REFERENCES academic_slots(id) ON DELETE CASCADE,
    reason TEXT,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_faculty_busy UNIQUE (faculty_id, block_date, academic_slot_id)
);
CREATE INDEX IF NOT EXISTS idx_busy_faculty_date
    ON faculty_busy_blocks(faculty_id, block_date);

-- ----------------------------------------------------------
-- queue_entries  —  live queue, token number, check-in, delay, ETA, exchange,
-- and the operational lifecycle beyond the 5 committed request statuses
-- (brief items 11-16, workflow items 7/11). Exactly one row per approved
-- appointment that has entered a faculty's dated queue session, identified by
-- (faculty_id, meeting_date, academic_slot_id). request_id links back to the
-- canonical `requests` row, which remains the committed source of truth.
--
-- `access_token_id` links to the canonical tokens row (token_type
-- 'REQUEST_ACCESS') generated on approval, so approval still writes to the real
-- schema table as well.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS queue_entries (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id BIGINT NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    faculty_id BIGINT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    meeting_date DATE NOT NULL,
    academic_slot_id BIGINT NOT NULL REFERENCES academic_slots(id) ON DELETE RESTRICT,
    token_number INT NOT NULL,                 -- human-facing queue ticket number
    access_token_id BIGINT REFERENCES tokens(id) ON DELETE SET NULL,
    priority_class VARCHAR(24) NOT NULL DEFAULT 'CONFIRMED',
    priority_score INT NOT NULL DEFAULT 0,
    -- Operational lifecycle (the sub-state the canonical requests.status cannot hold)
    state VARCHAR(24) NOT NULL DEFAULT 'WAITING'
        CHECK (state IN ('WAITING','CHECKED_IN','READY','IN_PROGRESS',
                         'COMPLETED','NO_SHOW','WITHDRAWN')),
    checked_in_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,                     -- actual meeting start
    completed_at TIMESTAMPTZ,                   -- actual meeting completion
    delay_minutes INT NOT NULL DEFAULT 0 CHECK (delay_minutes >= 0),
    exchanged_with_id BIGINT REFERENCES queue_entries(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- One queue entry per request; a request maps to exactly one dated slot.
    CONSTRAINT uq_queue_request UNIQUE (request_id),
    -- Token number is unique within a faculty's dated slot session.
    CONSTRAINT uq_queue_token UNIQUE (faculty_id, meeting_date, academic_slot_id, token_number)
);
CREATE INDEX IF NOT EXISTS idx_queue_session
    ON queue_entries(faculty_id, meeting_date, academic_slot_id);
CREATE INDEX IF NOT EXISTS idx_queue_state ON queue_entries(state);

-- ----------------------------------------------------------
-- Buffer + queue configuration seeded into the canonical system_settings table
-- (no new table needed). Application config supplies the default; a row here
-- overrides it. See app/services/buffer.py and app/core/config.py.
-- ----------------------------------------------------------
INSERT INTO system_settings (setting_key, setting_value, description, updated_by)
VALUES
  ('APPOINTMENT_BUFFER_MINUTES', '5',
   'Meeting buffer applied to free-slot calc, booking, reschedule and conflict checks.', 1),
  ('DEFAULT_MEETING_MINUTES', '15',
   'Default meeting duration used by the deterministic ETA when no override exists.', 1),
  ('QUEUE_BREAK_AFTER', '0',
   'Insert a break after N consecutive meetings in ETA (0 disables).', 1),
  ('QUEUE_BREAK_MINUTES', '5',
   'Break length in minutes used by the ETA when QUEUE_BREAK_AFTER > 0.', 1)
ON CONFLICT (setting_key) DO NOTHING;
