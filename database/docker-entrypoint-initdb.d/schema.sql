-- ==========================================================
-- CAMPUSFLOW AI DATABASE SCHEMA (DDL)
-- Production-ready, 3NF-compliant schema for PostgreSQL 15+
-- ==========================================================

-- Clean up existing tables if any (ordered to respect foreign key constraints)
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS system_settings CASCADE;
DROP TABLE IF EXISTS ai_logs CASCADE;
DROP TABLE IF EXISTS chat_history CASCADE;
DROP TABLE IF EXISTS approvals CASCADE;
DROP TABLE IF EXISTS department_requests CASCADE;
DROP TABLE IF EXISTS substitute_requests CASCADE;
DROP TABLE IF EXISTS faculty_requests CASCADE;
DROP TABLE IF EXISTS announcements CASCADE;
DROP TABLE IF EXISTS event_attendance CASCADE;
DROP TABLE IF EXISTS event_registrations CASCADE;
DROP TABLE IF EXISTS venue_bookings CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS club_members CASCADE;
DROP TABLE IF EXISTS clubs CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS tokens CASCADE;
DROP TABLE IF EXISTS requests CASCADE;
DROP TABLE IF EXISTS timetable CASCADE;
DROP TABLE IF EXISTS academic_slots CASCADE;
DROP TABLE IF EXISTS student_subjects CASCADE;
DROP TABLE IF EXISTS faculty_subjects CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS faculty CASCADE;
DROP TABLE IF EXISTS classrooms CASCADE;
DROP TABLE IF EXISTS subjects CASCADE;
DROP TABLE IF EXISTS sections CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS user_roles CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS roles CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;

-- ==========================================================
-- MODULE 1: AUTHENTICATION & ROLES
-- ==========================================================

CREATE TABLE roles (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive', 'Suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- User-Roles Bridge Table (Many-to-Many relationship)
CREATE TABLE user_roles (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

-- ==========================================================
-- MODULE 2: ACADEMIC INFORMATION
-- ==========================================================

CREATE TABLE departments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    head_faculty_id BIGINT, -- Circular dependency resolved by adding FK constraint post-table-creation
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sections (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    academic_year INT NOT NULL CHECK (academic_year >= 2000),
    semester VARCHAR(20) NOT NULL CHECK (semester IN ('Fall', 'Spring', 'Summer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_department_section UNIQUE (department_id, name, academic_year, semester)
);

CREATE TABLE subjects (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    credits INT NOT NULL CHECK (credits >= 0),
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE classrooms (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_number VARCHAR(50) NOT NULL UNIQUE,
    building VARCHAR(100) NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    type VARCHAR(50) NOT NULL CHECK (type IN ('Lecture Hall', 'Lab', 'Seminar Room', 'Classroom')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE faculty (
    id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    faculty_code VARCHAR(50) NOT NULL UNIQUE,
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    designation VARCHAR(100) NOT NULL,
    office_location VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add Circular Foreign Key for Department Head
ALTER TABLE departments 
ADD CONSTRAINT fk_head_faculty FOREIGN KEY (head_faculty_id) REFERENCES faculty(id) ON DELETE SET NULL;

CREATE TABLE students (
    id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    roll_number VARCHAR(50) NOT NULL UNIQUE,
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    section_id BIGINT REFERENCES sections(id) ON DELETE SET NULL,
    admission_year INT NOT NULL CHECK (admission_year >= 2000),
    current_semester INT NOT NULL CHECK (current_semester BETWEEN 1 AND 8),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Student-Subject Enrollment Bridge Table (Many-to-Many)
CREATE TABLE student_subjects (
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id BIGINT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'Enrolled' CHECK (status IN ('Enrolled', 'Completed', 'Dropped')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_id, subject_id)
);

-- Faculty-Subject Assignment Bridge Table (Many-to-Many)
CREATE TABLE faculty_subjects (
    faculty_id BIGINT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    subject_id BIGINT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    section_id BIGINT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    academic_year INT NOT NULL CHECK (academic_year >= 2000),
    semester VARCHAR(20) NOT NULL CHECK (semester IN ('Fall', 'Spring', 'Summer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (faculty_id, subject_id, section_id, academic_year, semester)
);

-- ==========================================================
-- MODULE 3: TIMETABLE
-- ==========================================================

CREATE TABLE academic_slots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slot_name VARCHAR(50) NOT NULL UNIQUE,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_times CHECK (start_time < end_time)
);

-- Timetable stored row-wise
CREATE TABLE timetable (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    section_id BIGINT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    subject_id BIGINT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    faculty_id BIGINT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    classroom_id BIGINT NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
    academic_slot_id BIGINT NOT NULL REFERENCES academic_slots(id) ON DELETE RESTRICT,
    day_of_week VARCHAR(15) NOT NULL CHECK (day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
    academic_year INT NOT NULL CHECK (academic_year >= 2000),
    semester VARCHAR(20) NOT NULL CHECK (semester IN ('Fall', 'Spring', 'Summer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Hard scheduling constraints: prevent double-booking at DB level
    CONSTRAINT uq_timetable_classroom UNIQUE (classroom_id, day_of_week, academic_slot_id, academic_year, semester),
    CONSTRAINT uq_timetable_faculty UNIQUE (faculty_id, day_of_week, academic_slot_id, academic_year, semester),
    CONSTRAINT uq_timetable_section UNIQUE (section_id, day_of_week, academic_slot_id, academic_year, semester)
);

-- ==========================================================
-- MODULE 4: STUDENT ↔ FACULTY COORDINATION (CORE MVP)
-- ==========================================================

CREATE TABLE requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    faculty_id BIGINT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    request_type VARCHAR(50) NOT NULL CHECK (request_type IN ('Appointment', 'Recommendation Letter', 'Project Approval', 'Grade Query', 'Other')),
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected', 'Cancelled', 'Rescheduled')),
    scheduled_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tokens (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_value VARCHAR(255) NOT NULL UNIQUE,
    token_type VARCHAR(50) NOT NULL CHECK (token_type IN ('API_KEY', 'PASSWORD_RESET', 'EMAIL_VERIFICATION', 'REQUEST_ACCESS')),
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notifications (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('REQUEST_UPDATE', 'EVENT_INVITATION', 'ALERT', 'SYSTEM')),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- MODULE 5: CLUB COORDINATION
-- ==========================================================

CREATE TABLE clubs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50) NOT NULL CHECK (category IN ('Technical', 'Cultural', 'Sports', 'Social', 'Academic')),
    mentor_faculty_id BIGINT REFERENCES faculty(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE club_members (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    club_id BIGINT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'Member' CHECK (role IN ('President', 'Vice President', 'Treasurer', 'Secretary', 'Core Member', 'Member')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_club_student UNIQUE (club_id, student_id)
);

CREATE TABLE events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    organizing_club_id BIGINT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Pending Approval' CHECK (status IN ('Draft', 'Pending Approval', 'Approved', 'Rejected', 'Cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_event_times CHECK (start_time < end_time)
);

CREATE TABLE venue_bookings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id BIGINT REFERENCES events(id) ON DELETE SET NULL,
    classroom_id BIGINT NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
    booked_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    purpose VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_booking_times CHECK (start_time < end_time)
);
-- ==========================================================
-- CLUB EVENT REGISTRATIONS
-- ==========================================================

CREATE TABLE event_registrations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    event_id BIGINT NOT NULL
        REFERENCES events(id) ON DELETE CASCADE,

    student_id BIGINT NOT NULL
        REFERENCES students(id) ON DELETE CASCADE,

    registered_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    status VARCHAR(20) NOT NULL
        DEFAULT 'Registered'
        CHECK (status IN ('Registered', 'Cancelled')),

    CONSTRAINT uq_event_student_registration
        UNIQUE (event_id, student_id)
);
-- ==========================================================
-- CLUB EVENT ATTENDANCE
-- ==========================================================

CREATE TABLE event_attendance (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    event_id BIGINT NOT NULL
        REFERENCES events(id) ON DELETE CASCADE,

    student_id BIGINT NOT NULL
        REFERENCES students(id) ON DELETE CASCADE,

    marked_by_user_id BIGINT NOT NULL
        REFERENCES users(id) ON DELETE CASCADE,

    marked_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    status VARCHAR(20) NOT NULL
        DEFAULT 'Present'
        CHECK (status IN ('Present', 'Absent')),

    CONSTRAINT uq_event_attendance
        UNIQUE (event_id, student_id)
);
-- ==========================================================
-- CLUB ANNOUNCEMENTS
-- ==========================================================

CREATE TABLE announcements (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    club_id BIGINT NOT NULL
        REFERENCES clubs(id) ON DELETE CASCADE,

    title VARCHAR(150) NOT NULL,

    message TEXT NOT NULL,

    target VARCHAR(30) NOT NULL
        DEFAULT 'ALL_MEMBERS'
        CHECK (
            target IN (
                'ALL_MEMBERS',
                'PARTICIPANTS',
                'FACULTY',
                'COORDINATORS'
            )
        ),

    is_published BOOLEAN NOT NULL
        DEFAULT FALSE,

    published_at TIMESTAMPTZ,

    created_by_user_id BIGINT NOT NULL
        REFERENCES users(id) ON DELETE CASCADE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);
-- ==========================================================
-- MODULE 6: FACULTY COORDINATION
-- ==========================================================

CREATE TABLE faculty_requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sender_faculty_id BIGINT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    receiver_faculty_id BIGINT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    request_type VARCHAR(50) NOT NULL CHECK (request_type IN ('Co-teaching', 'Resource Share', 'Duty Exchange', 'Research Collaboration', 'Other')),
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE substitute_requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    faculty_request_id BIGINT NOT NULL REFERENCES faculty_requests(id) ON DELETE CASCADE,
    timetable_id BIGINT NOT NULL REFERENCES timetable(id) ON DELETE CASCADE,
    date_of_substitute DATE NOT NULL,
    proposed_substitute_faculty_id BIGINT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Accepted', 'Declined', 'Cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- MODULE 7: DEPARTMENT COORDINATION
-- ==========================================================

CREATE TABLE department_requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sender_department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    receiver_department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    request_type VARCHAR(50) NOT NULL CHECK (request_type IN ('Curriculum Change', 'Resource Sharing', 'Interdisciplinary Event', 'Other')),
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE approvals (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_request_id BIGINT REFERENCES department_requests(id) ON DELETE CASCADE,
    venue_booking_id BIGINT REFERENCES venue_bookings(id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    approver_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('Approved', 'Rejected')),
    remarks TEXT,
    action_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure an approval is tied to exactly one workflow request type (XOR condition)
    CONSTRAINT chk_single_approval_target CHECK (
        (department_request_id IS NOT NULL AND venue_booking_id IS NULL AND event_id IS NULL) OR
        (department_request_id IS NULL AND venue_booking_id IS NOT NULL AND event_id IS NULL) OR
        (department_request_id IS NULL AND venue_booking_id IS NULL AND event_id IS NOT NULL)
    )
);

-- ==========================================================
-- MODULE 8: AI & CHAT INTERACTION LOGS
-- ==========================================================

CREATE TABLE chat_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) NOT NULL,
    message_role VARCHAR(20) NOT NULL CHECK (message_role IN ('user', 'assistant', 'system')),
    message_content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ai_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    service_name VARCHAR(100) NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    tokens_used INT CHECK (tokens_used >= 0),
    latency_ms INT CHECK (latency_ms >= 0),
    status VARCHAR(20) NOT NULL CHECK (status IN ('Success', 'Failure')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- ============================================================
-- AI KNOWLEDGE BASE
-- ============================================================

CREATE TABLE ai_knowledge_base (
    id BIGINT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category VARCHAR(100),
    tags VARCHAR(255),
    embedding_vector VECTOR(1536),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);


-- ============================================================
-- AI CHAT HISTORY
-- ============================================================

CREATE TABLE ai_chat_history (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    message_role VARCHAR(50) NOT NULL,
    message_content TEXT NOT NULL,
    created_at TIMESTAMP
);


-- ============================================================
-- AI FEEDBACK
-- ============================================================

CREATE TABLE ai_feedback (
    id BIGINT PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP,

    CONSTRAINT fk_ai_feedback_chat
        FOREIGN KEY (chat_id)
        REFERENCES ai_chat_history(id)
);


-- ============================================================
-- AI PRIORITY DECISIONS
-- ============================================================

CREATE TABLE priority_decisions (
    id BIGINT PRIMARY KEY,
    appointment_id BIGINT NOT NULL,
    priority_score INTEGER NOT NULL,
    decision_reason TEXT NOT NULL,
    engine_used VARCHAR(100) DEFAULT 'AIPriorityEngine_v1',
    created_at TIMESTAMP
);
-- ==========================================================
-- MODULE 9: AUDIT LOGS & SYSTEM SETTINGS
-- ==========================================================

CREATE TABLE audit_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    record_id BIGINT NOT NULL,
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_settings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT NOT NULL,
    description TEXT,
    updated_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- ==========================================================
-- queue_entries table 
-- ==========================================================
CREATE TABLE queue_entries (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    request_id BIGINT NOT NULL UNIQUE
        REFERENCES requests(id) ON DELETE CASCADE,

    faculty_id BIGINT NOT NULL
        REFERENCES faculty(id) ON DELETE CASCADE,

    student_id BIGINT NOT NULL
        REFERENCES students(id) ON DELETE CASCADE,

    meeting_date DATE NOT NULL,

    academic_slot_id BIGINT NOT NULL
        REFERENCES academic_slots(id) ON DELETE RESTRICT,

    token_number INT NOT NULL,

    access_token_id BIGINT
        REFERENCES tokens(id) ON DELETE SET NULL,

    priority_class VARCHAR(24) NOT NULL
        DEFAULT 'CONFIRMED',

    priority_score INT NOT NULL
        DEFAULT 0,

    state VARCHAR(24) NOT NULL
        DEFAULT 'WAITING',

    checked_in_at TIMESTAMPTZ,

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    delay_minutes INT NOT NULL
        DEFAULT 0,

    exchanged_with_id BIGINT
        REFERENCES queue_entries(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_queue_request
        UNIQUE (request_id),

    CONSTRAINT uq_queue_token
        UNIQUE (
            faculty_id,
            meeting_date,
            academic_slot_id,
            token_number
        ),

    CONSTRAINT chk_queue_state
        CHECK (
            state IN (
                'WAITING',
                'CHECKED_IN',
                'READY',
                'IN_PROGRESS',
                'COMPLETED',
                'NO_SHOW',
                'WITHDRAWN'
            )
        )
);
-- ==========================================================
-- faculty_busy_blocks
-- ==========================================================
CREATE TABLE faculty_busy_blocks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES faculty(id) ON DELETE CASCADE,

    block_date DATE NOT NULL,

    academic_slot_id BIGINT NOT NULL
        REFERENCES academic_slots(id) ON DELETE CASCADE,

    reason TEXT,

    created_by BIGINT
        REFERENCES users(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_faculty_busy
        UNIQUE (
            faculty_id,
            block_date,
            academic_slot_id
        )
);

-- ==========================================================
-- MODULE 10: PLACEMENT COORDINATION
-- ==========================================================

CREATE TABLE placement_announcements (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    title VARCHAR(200) NOT NULL,
    company VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,

    drive_date DATE,
    registration_deadline TIMESTAMPTZ,
    registration_link VARCHAR(500),

    min_cgpa NUMERIC(4,2),
    backlogs_allowed INT,

    target_type VARCHAR(20) NOT NULL DEFAULT 'ALL'
        CHECK (target_type IN ('ALL', 'DEPARTMENT', 'SECTION', 'SELECTED')),

    department_id BIGINT
        REFERENCES departments(id) ON DELETE SET NULL,

    section VARCHAR(50),

    target_student_ids JSONB,

    created_by BIGINT NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'CLOSED')),

    CONSTRAINT chk_placement_cgpa
        CHECK (min_cgpa IS NULL OR (min_cgpa >= 0 AND min_cgpa <= 10)),

    CONSTRAINT chk_placement_backlogs
        CHECK (backlogs_allowed IS NULL OR backlogs_allowed >= 0)
);

CREATE INDEX idx_placement_created_by
    ON placement_announcements(created_by);

CREATE INDEX idx_placement_department
    ON placement_announcements(department_id);

CREATE INDEX idx_placement_status
    ON placement_announcements(status);

CREATE INDEX idx_placement_drive_date
    ON placement_announcements(drive_date);
-- ==========================================================
-- PERFORMANCE INDEXES (Optimized for ERP queries and foreign keys)
-- ==========================================================

-- Authentication & Users
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- Academic Information
CREATE INDEX idx_sections_department ON sections(department_id);
CREATE INDEX idx_subjects_department ON subjects(department_id);
CREATE INDEX idx_faculty_department ON faculty(department_id);
CREATE INDEX idx_students_department ON students(department_id);
CREATE INDEX idx_students_section ON students(section_id);

-- Timetable
CREATE INDEX idx_timetable_section ON timetable(section_id);
CREATE INDEX idx_timetable_subject ON timetable(subject_id);
CREATE INDEX idx_timetable_faculty ON timetable(faculty_id);
CREATE INDEX idx_timetable_classroom ON timetable(classroom_id);
CREATE INDEX idx_timetable_slot ON timetable(academic_slot_id);
CREATE INDEX idx_timetable_lookup ON timetable(day_of_week, academic_year, semester);

-- Requests (Student ↔ Faculty)
CREATE INDEX idx_requests_student ON requests(student_id);
CREATE INDEX idx_requests_faculty ON requests(faculty_id);
CREATE INDEX idx_requests_status ON requests(status);

-- Token & Notifications
CREATE INDEX idx_tokens_value ON tokens(token_value);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id) WHERE (is_read = FALSE);

-- Clubs & Events
CREATE INDEX idx_club_members_student ON club_members(student_id);
CREATE INDEX idx_events_club ON events(organizing_club_id);
CREATE INDEX idx_events_start_end ON events(start_time, end_time);
CREATE INDEX idx_venue_bookings_classroom ON venue_bookings(classroom_id);
CREATE INDEX idx_venue_bookings_status ON venue_bookings(status);
CREATE INDEX idx_event_registrations_event
    ON event_registrations(event_id);

CREATE INDEX idx_event_registrations_student
    ON event_registrations(student_id);

CREATE INDEX idx_event_attendance_event
    ON event_attendance(event_id);

CREATE INDEX idx_event_attendance_student
    ON event_attendance(student_id);

CREATE INDEX idx_announcements_club
    ON announcements(club_id);

CREATE INDEX idx_announcements_created_by
    ON announcements(created_by_user_id);

-- Faculty Requests
CREATE INDEX idx_faculty_requests_sender ON faculty_requests(sender_faculty_id);
CREATE INDEX idx_faculty_requests_receiver ON faculty_requests(receiver_faculty_id);
CREATE INDEX idx_substitute_requests_proposed ON substitute_requests(proposed_substitute_faculty_id);

-- Department Requests
CREATE INDEX idx_dept_requests_sender ON department_requests(sender_department_id);
CREATE INDEX idx_dept_requests_receiver ON department_requests(receiver_department_id);

-- Approvals
CREATE INDEX idx_approvals_dept_req ON approvals(department_request_id) WHERE (department_request_id IS NOT NULL);
CREATE INDEX idx_approvals_venue ON approvals(venue_booking_id) WHERE (venue_booking_id IS NOT NULL);
CREATE INDEX idx_approvals_event ON approvals(event_id) WHERE (event_id IS NOT NULL);

-- Logs & AI
CREATE INDEX idx_chat_history_session ON chat_history(session_id);
CREATE INDEX idx_ai_logs_service ON ai_logs(service_name);
CREATE INDEX idx_audit_logs_table_record ON audit_logs(table_name, record_id);
CREATE INDEX idx_ai_knowledge_base_category
    ON ai_knowledge_base(category);

CREATE INDEX idx_ai_chat_history_user_id
    ON ai_chat_history(user_id);

CREATE INDEX idx_ai_chat_history_session_id
    ON ai_chat_history(session_id);

CREATE INDEX idx_priority_decisions_appointment_id
    ON priority_decisions(appointment_id);


-- Queue Entries
CREATE INDEX idx_queue_faculty
    ON queue_entries(faculty_id);

CREATE INDEX idx_queue_student
    ON queue_entries(student_id);

CREATE INDEX idx_queue_request
    ON queue_entries(request_id);

CREATE INDEX idx_queue_slot
    ON queue_entries(academic_slot_id);

CREATE INDEX idx_queue_meeting_date
    ON queue_entries(meeting_date);

CREATE INDEX idx_queue_state
    ON queue_entries(state);

CREATE INDEX idx_queue_faculty_date
    ON queue_entries(faculty_id, meeting_date);

CREATE INDEX idx_queue_faculty_slot
    ON queue_entries(faculty_id, meeting_date, academic_slot_id);

CREATE INDEX idx_queue_token_lookup
    ON queue_entries(
        faculty_id,
        meeting_date,
        academic_slot_id,
        token_number
    );
-- Faculty Busy Blocks
CREATE INDEX idx_busy_faculty
    ON faculty_busy_blocks(faculty_id);

CREATE INDEX idx_busy_date
    ON faculty_busy_blocks(block_date);

CREATE INDEX idx_busy_slot
    ON faculty_busy_blocks(academic_slot_id);

CREATE INDEX idx_busy_lookup
    ON faculty_busy_blocks(
        faculty_id,
        block_date,
        academic_slot_id
    );

