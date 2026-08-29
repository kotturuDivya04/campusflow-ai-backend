-- ==========================================================
-- CAMPUSFLOW AI DATABASE SEED DATA
-- Populate tables with realistic data for local testing
-- ==========================================================

-- Clean insert blocks (using TRUNCATE to reset sequences in test environments, if needed)
-- We will just insert since schema.sql dropped all tables first.

-- 1. Roles
INSERT INTO roles (name, description) VALUES
('SuperAdmin', 'System administrator with full control over all modules'),
('DepartmentAdmin', 'Faculty or administrative head managing a department'),
('Faculty', 'Academic teaching staff members'),
('ClubLead', 'Student coordinator responsible for club events and activities'),
('Student', 'Enrolled student attending classes'),
('PlacementCoordinator', 'Faculty responsible for managing placement announcements');

-- 2. Users (Passwords are pre-hashed representations of 'password123')
INSERT INTO users (username, email, password_hash, first_name, last_name, phone, status) VALUES
('sysadmin', 'admin@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'System', 'Admin', '+15550100', 'Active'),
('aturing', 'alan.turing@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'Alan', 'Turing', '+15550101', 'Active'),
('ghopper', 'grace.hopper@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'Grace', 'Hopper', '+15550102', 'Active'),
('ntesla', 'nikola.tesla@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'Nikola', 'Tesla', '+15550103', 'Active'),
('jwatt', 'james.watt@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'James', 'Watt', '+15550104', 'Active'),
('ajones', 'alice.jones@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'Alice', 'Jones', '+15550201', 'Active'),
('bsmith', 'bob.smith@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'Bob', 'Smith', '+15550202', 'Active'),
('cwhite', 'charlie.white@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'Charlie', 'White', '+15550203', 'Active'),
('djohnson', 'david.johnson@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'David', 'Johnson', '+15550204', 'Active'),
('emiller', 'emma.miller@campusflow.edu', '$2b$12$K3y6Qh9iHq.Yd6Xf7h/e8Oxl5U6dGf0K7mZ2SgV9fG5a7K3B7Y8G2', 'Emma', 'Miller', '+15550205', 'Active');

-- 3. User-Roles Mapping

INSERT INTO user_roles (user_id, role_id) VALUES
(1, 1), -- sysadmin -> SuperAdmin
(2, 2), -- aturing -> DepartmentAdmin
(2, 3), -- aturing -> Faculty
(3, 3), -- ghopper -> Faculty
(3, 6), -- ghopper -> PlacementCoordinator
(4, 2), -- ntesla -> DepartmentAdmin
(4, 3), -- ntesla -> Faculty
(5, 3), -- jwatt -> Faculty
(6, 4), -- ajones -> ClubLead
(6, 5), -- ajones -> Student
(7, 5), -- bsmith -> Student
(8, 5), -- cwhite -> Student
(9, 5), -- djohnson -> Student
(10, 5); -- emiller -> Student

-- 4. Departments
INSERT INTO departments (code, name, description) VALUES
('CS', 'Computer Science & Engineering', 'Department of computing systems, software development, and AI studies'),
('EE', 'Electrical Engineering', 'Department covering power engineering, electronics, systems theory, and automation'),
('ME', 'Mechanical Engineering', 'Department handling thermodynamics, machine dynamics, and mechanical design');

-- 5. Faculty Profiles (mapped one-to-one with users)
INSERT INTO faculty (id, faculty_code, department_id, designation, office_location) VALUES
(2, 'FAC_CS_01', 1, 'Professor & Head', 'Turing Block, Room 402'),
(3, 'FAC_CS_02', 1, 'Associate Professor', 'Hopper Lab, Room 204'),
(4, 'FAC_EE_01', 2, 'Professor & Head', 'Tesla Labs, Room 101'),
(5, 'FAC_ME_01', 3, 'Assistant Professor', 'Watt Workshop, Room 12');

-- Update head_faculty_id in departments now that faculty profiles are loaded
UPDATE departments SET head_faculty_id = 2 WHERE code = 'CS';
UPDATE departments SET head_faculty_id = 4 WHERE code = 'EE';

-- 6. Sections
INSERT INTO sections (name, department_id, academic_year, semester) VALUES
('CS-A', 1, 2026, 'Fall'),
('CS-B', 1, 2026, 'Fall'),
('EE-A', 2, 2026, 'Fall'),
('ME-A', 3, 2026, 'Fall');

-- 7. Subjects
INSERT INTO subjects (code, name, description, credits, department_id) VALUES
('CS-101', 'Introduction to Computing', 'Basic principles of computation and programming', 4, 1),
('CS-202', 'Data Structures & Algorithms', 'Techniques for organizing data efficiently', 4, 1),
('EE-101', 'Electrical Circuits', 'Network analysis, circuit theorems, and transients', 3, 2),
('ME-101', 'Basic Thermodynamics', 'First and second laws of thermodynamics, cycles', 3, 3);

-- 8. Classrooms
INSERT INTO classrooms (room_number, building, capacity, type) VALUES
('LH-101', 'Main Academic Building', 60, 'Lecture Hall'),
('LH-102', 'Main Academic Building', 45, 'Lecture Hall'),
('CS-LAB-1', 'Turing Block', 30, 'Lab'),
('SEM-301', 'Tesla Building', 25, 'Seminar Room');

-- 9. Students (mapped one-to-one with users)
-- CS-A ID is 1, CS-B is 2, EE-A is 3, ME-A is 4
INSERT INTO students (id, roll_number, department_id, section_id, admission_year, current_semester) VALUES
(6, '2026_CS_001', 1, 1, 2026, 1),
(7, '2026_CS_002', 1, 1, 2026, 1),
(8, '2026_CS_015', 1, 2, 2026, 1),
(9, '2026_EE_001', 2, 3, 2026, 1),
(10, '2026_ME_001', 3, 4, 2026, 1);

-- 10. Student-Subject Enrollments
INSERT INTO student_subjects (student_id, subject_id, status) VALUES
(6, 1, 'Enrolled'),
(6, 2, 'Enrolled'),
(7, 1, 'Enrolled'),
(7, 2, 'Enrolled'),
(8, 2, 'Enrolled'),
(9, 3, 'Enrolled'),
(10, 4, 'Enrolled');

-- 11. Faculty-Subject Assignments
-- Alan Turing (id=2) teaches CS-101 to CS-A
-- Grace Hopper (id=3) teaches CS-202 to CS-A and CS-B
-- Nikola Tesla (id=4) teaches EE-101 to EE-A
-- James Watt (id=5) teaches ME-101 to ME-A
INSERT INTO faculty_subjects (faculty_id, subject_id, section_id, academic_year, semester) VALUES
(2, 1, 1, 2026, 'Fall'),
(3, 2, 1, 2026, 'Fall'),
(3, 2, 2, 2026, 'Fall'),
(4, 3, 3, 2026, 'Fall'),
(5, 4, 4, 2026, 'Fall');

-- 12. Academic Slots (Daily Schedule)
INSERT INTO academic_slots (slot_name, start_time, end_time) VALUES
('Period 1', '08:30:00', '09:20:00'),
('Period 2', '09:30:00', '10:20:00'),
('Period 3', '10:30:00', '11:20:00'),
('Period 4', '11:30:00', '12:20:00'),
('Period 5', '13:30:00', '14:20:00'),
('Period 6', '14:30:00', '15:20:00'),
('Period 7', '15:30:00', '16:20:00');

-- Faculty Busy Blocks
INSERT INTO faculty_busy_blocks (
    faculty_id,
    block_date,
    academic_slot_id,
    reason,
    created_by
)
VALUES
(2, '2026-08-01', 5, 'Department Meeting', 2),
(3, '2026-08-01', 6, 'Research Presentation', 3);

-- 13. Timetable (Row-wise Schedule)
-- Section 1 (CS-A): Period 1 & 2 on Monday (CS-101 by Alan Turing in LH-101)
-- Section 1 (CS-A): Period 3 on Monday (CS-202 by Grace Hopper in LH-102)
-- Section 2 (CS-B): Period 4 on Monday (CS-202 by Grace Hopper in CS-LAB-1)
-- Section 3 (EE-A): Period 1 on Tuesday (EE-101 by Nikola Tesla in SEM-301)
-- Section 4 (ME-A): Period 2 on Tuesday (ME-101 by James Watt in LH-102)
INSERT INTO timetable (section_id, subject_id, faculty_id, classroom_id, academic_slot_id, day_of_week, academic_year, semester) VALUES
(1, 1, 2, 1, 1, 'Monday', 2026, 'Fall'),
(1, 1, 2, 1, 2, 'Monday', 2026, 'Fall'),
(1, 2, 3, 2, 3, 'Monday', 2026, 'Fall'),
(2, 2, 3, 3, 4, 'Monday', 2026, 'Fall'),
(3, 3, 4, 4, 1, 'Tuesday', 2026, 'Fall'),
(4, 4, 5, 2, 2, 'Tuesday', 2026, 'Fall');

-- 14. Requests (Student ↔ Faculty Coordination)
INSERT INTO requests (student_id, faculty_id, request_type, title, description, status, scheduled_time) VALUES
(6, 2, 'Appointment', 'Discuss Term Project Idea', 'Requesting a 15-minute slot to finalize my project topic on Turing Machines.', 'Approved', '2026-08-01 14:00:00+00'),
(7, 2, 'Recommendation Letter', 'Recommendation Letter for Internship', 'Need a reference letter for a research position at Bell Labs.', 'Pending', NULL),
(8, 3, 'Grade Query', 'Midterm Grade Discrepancy', 'I noticed a calculation error in my Question 3 grading.', 'Pending', NULL),
(6, 3, 'Appointment', 'Final Exam Prep advice', 'Need guidance on key focus areas for Data Structures exam.', 'Rejected', NULL);



-- 15. Tokens (User tokens for API/Reset)
INSERT INTO tokens (user_id, token_value, token_type, expires_at, is_active) VALUES
(6, 'apikey_student_alice_xyz123abc789', 'API_KEY', '2027-01-01 00:00:00+00', TRUE),
(2, 'pwdreset_turing_abcde54321', 'PASSWORD_RESET', '2026-07-17 12:00:00+00', TRUE);

-- queue_entries
INSERT INTO queue_entries (
    request_id,
    faculty_id,
    student_id,
    meeting_date,
    academic_slot_id,
    token_number,
    priority_class,
    priority_score,
    state,
    delay_minutes
)
VALUES
(1, 2, 6, '2026-08-01', 5, 1, 'CONFIRMED', 100, 'WAITING', 0),

(2, 2, 7, '2026-08-01', 5, 2, 'CONFIRMED', 90, 'WAITING', 0),

(3, 3, 8, '2026-08-01', 6, 1, 'CONFIRMED', 95, 'CHECKED_IN', 0),

(4, 3, 6, '2026-08-01', 6, 2, 'CONFIRMED', 80, 'READY', 5);

-- 16. Notifications
INSERT INTO notifications (user_id, title, message, type, is_read) VALUES
(6, 'Appointment Approved', 'Your meeting with Dr. Alan Turing has been scheduled for 2026-07-20 at 14:00.', 'REQUEST_UPDATE', FALSE),
(2, 'New Request Received', 'Student Alice Jones submitted a Recommendation Letter request.', 'REQUEST_UPDATE', FALSE),
(7, 'System Maintenance Notice', 'The CampusFlow system will undergo scheduled database maintenance this Saturday.', 'SYSTEM', FALSE);

-- 17. Clubs
INSERT INTO clubs (name, description, category, mentor_faculty_id) VALUES
('Bytes & Logic Club', 'Official Computer Science club focusing on programming competitions and AI hacks.', 'Technical', 2),
('VoltBots Robotics', 'Interdisciplinary club focused on building robots and automation solutions.', 'Technical', 4);

-- 18. Club Members
-- Alice Jones (id=6) is President of Bytes & Logic
-- Bob Smith (id=7) is Treasurer of Bytes & Logic
-- Charlie White (id=8) is Member of VoltBots
INSERT INTO club_members (club_id, student_id, role, is_active) VALUES
(1, 6, 'President', TRUE),
(1, 7, 'Treasurer', TRUE),
(2, 8, 'Member', TRUE),
(2, 6, 'Core Member', TRUE);

-- 19. Events
INSERT INTO events (title, description, organizing_club_id, start_time, end_time, status) VALUES
('Autumn AI Hackathon 2026', 'A 24-hour campus-wide AI hackathon to solve coordination problems.', 1, '2026-10-10 09:00:00+00', '2026-10-11 12:00:00+00', 'Approved'),
('RoboWars Championship', 'Annual arena combat tournament between student built robots.', 2, '2026-11-05 10:00:00+00', '2026-11-05 18:00:00+00', 'Pending Approval');

-- 20. Venue Bookings
INSERT INTO venue_bookings (event_id, classroom_id, booked_by_user_id, start_time, end_time, purpose, status) VALUES
(1, 1, 6, '2026-10-10 08:00:00+00', '2026-10-11 13:00:00+00', 'Venue setup and hackathon execution', 'Approved'),
(2, 4, 6, '2026-11-05 09:00:00+00', '2026-11-05 19:00:00+00', 'RoboWars battles and spectator seats', 'Pending');

-- 20A. Event Registrations
INSERT INTO event_registrations
    (event_id, student_id, registered_at, status)
VALUES
    (1, 6, '2026-10-01 10:00:00+00', 'Registered'),
    (1, 7, '2026-10-01 10:15:00+00', 'Registered'),
    (1, 8, '2026-10-01 10:30:00+00', 'Registered'),
    (2, 8, '2026-10-20 11:00:00+00', 'Registered');
    
-- 20B. Event Attendance
INSERT INTO event_attendance
    (event_id, student_id, marked_by_user_id, marked_at, status)
VALUES
    (1, 6, 6, '2026-10-10 09:30:00+00', 'Present'),
    (1, 7, 6, '2026-10-10 09:35:00+00', 'Present'),
    (1, 8, 6, '2026-10-10 09:40:00+00', 'Absent');

-- 20C. Club Announcements
INSERT INTO announcements
    (
        club_id,
        title,
        message,
        target,
        is_published,
        published_at,
        created_by_user_id
    )
VALUES
    (
        1,
        'AI Hackathon Registration Open',
        'Registrations are now open for the Autumn AI Hackathon 2026.',
        'ALL_MEMBERS',
        TRUE,
        '2026-10-01 09:00:00+00',
        6
    ),
    (
        2,
        'RoboWars Preparation Meeting',
        'All VoltBots members are requested to attend the preparation meeting.',
        'ALL_MEMBERS',
        TRUE,
        '2026-10-25 10:00:00+00',
        6
    ),
    (
        1,
        'Faculty Mentoring Session',
        'A faculty mentoring session will be conducted for club coordinators.',
        'COORDINATORS',
        TRUE,
        '2026-10-05 12:00:00+00',
        2
    );

-- 21. Faculty Requests (Faculty ↔ Faculty Coordination)
INSERT INTO faculty_requests (sender_faculty_id, receiver_faculty_id, request_type, title, description, status) VALUES
(3, 2, 'Co-teaching', 'Co-teaching request for CS Advanced Seminar', 'Would love to deliver two lectures on Lambda Calculus in your class.', 'Approved'),
(5, 3, 'Resource Share', 'Lab Equipment access', 'Requesting access to the CS Cluster computing units for thermodynamic modeling.', 'Pending');

-- 22. Substitute Requests
-- Grace Hopper (id=3) requesting Nikola Tesla (id=4) to take her class (timetable_id=3) on 2026-09-14
INSERT INTO substitute_requests (faculty_request_id, timetable_id, date_of_substitute, proposed_substitute_faculty_id, status) VALUES
(1, 3, '2026-09-14', 4, 'Pending');

-- 23. Department Requests (Department ↔ Department Coordination)
INSERT INTO department_requests (sender_department_id, receiver_department_id, request_type, title, description, status) VALUES
(1, 2, 'Resource Sharing', 'Interdisciplinary Robotics course lab sharing', 'CS requests access to EE Circuit Simulation software for joint course CS-310.', 'Approved'),
(3, 1, 'Curriculum Change', 'Review of programming requirement for Mechanical Engineers', 'Requesting CS faculty review our draft python programming course syllabus.', 'Pending');

-- 24. Approvals (Centralized Approval History)
INSERT INTO approvals (department_request_id, venue_booking_id, event_id, approver_user_id, status, remarks) VALUES
(1, NULL, NULL, 4, 'Approved', 'EE department is happy to share access. Licenses verified.'),
(NULL, 1, NULL, 2, 'Approved', 'Turing hall capacity verified. Approved under club guidelines.');

-- 25. Chat History (AI interface interactions)
INSERT INTO chat_history (user_id, session_id, message_role, message_content) VALUES
(6, 'sess_ab123', 'user', 'Who is Dr. Alan Turings next appointment?'),
(6, 'sess_ab123', 'assistant', 'Dr. Alan Turings next approved appointment is with student Alice Jones on 2026-07-20 at 14:00.'),
(6, 'sess_ab123', 'user', 'Where is his office located?'),
(6, 'sess_ab123', 'assistant', 'His office is located in Turing Block, Room 402.');

-- 26. AI Logs
INSERT INTO ai_logs (user_id, service_name, prompt, response, tokens_used, latency_ms, status, error_message) VALUES
(6, 'NLPCoordinator', 'Who is Dr. Alan Turings next appointment?', 'Lookup resolved. Dr. Alan Turings next approved appointment is with student Alice Jones on 2026-07-20 at 14:00.', 150, 480, 'Success', NULL),
(2, 'TimetableParser', 'File: CS_Timetable.pdf uploaded by aturing', 'Successfully parsed 42 class periods and mapped to sections CS-A and CS-B.', 1200, 2450, 'Success', NULL);

-- 27. Audit Logs
INSERT INTO audit_logs (user_id, action, table_name, record_id, old_values, new_values, ip_address) VALUES
(1, 'INSERT', 'users', 6, NULL, '{"username": "ajones", "email": "alice.jones@campusflow.edu"}', '192.168.1.50'),
(2, 'UPDATE', 'departments', 1, '{"head_faculty_id": null}', '{"head_faculty_id": 2}', '192.168.1.100');

-- 28. System Settings
INSERT INTO system_settings (setting_key, setting_value, description, updated_by) VALUES
('CURRENT_ACADEMIC_YEAR', '2026', 'The active academic year of the university.', 1),
('CURRENT_SEMESTER', 'Fall', 'The current active semester (Fall, Spring, Summer).', 1),
('MAINTENANCE_MODE', 'FALSE', 'Global switch to set system to read-only during system upgrades.', 1);

-- ==========================================================
-- 29. AI KNOWLEDGE BASE
-- ==========================================================

INSERT INTO ai_knowledge_base
    (title, question, answer, category, tags, created_at, updated_at)
VALUES
(
    'Attendance Policy',
    'What is the minimum attendance required?',
    'Students must maintain the minimum attendance requirement specified by the university academic regulations.',
    'Academic',
    'attendance,academic,students',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'Library Rules',
    'How long can a student borrow a book?',
    'Students can borrow library books according to the borrowing period defined by the university library.',
    'Library',
    'library,books,borrowing',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'Event Registration',
    'How can I register for a campus event?',
    'Students can register for available campus events through the CampusFlow event registration system.',
    'Events',
    'events,registration,clubs',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);


-- ==========================================================
-- 30. AI CHAT HISTORY
-- ==========================================================

INSERT INTO ai_chat_history
    (user_id, session_id, message_role, message_content, created_at)
VALUES
(
    6,
    'ai_session_001',
    'user',
    'How can I register for a campus event?',
    CURRENT_TIMESTAMP
),
(
    6,
    'ai_session_001',
    'assistant',
    'You can register for an available campus event through the CampusFlow event registration system.',
    CURRENT_TIMESTAMP
),
(
    7,
    'ai_session_002',
    'user',
    'What are the library rules?',
    CURRENT_TIMESTAMP
),
(
    7,
    'ai_session_002',
    'assistant',
    'You can check the university library rules through the CampusFlow knowledge resources.',
    CURRENT_TIMESTAMP
);


-- ==========================================================
-- 31. AI FEEDBACK
-- ==========================================================

INSERT INTO ai_feedback
    (chat_id, user_id, rating, comment, created_at)
VALUES
(
    1,
    6,
    5,
    'The answer was clear and helpful.',
    CURRENT_TIMESTAMP
),
(
    3,
    7,
    4,
    'The response was useful but could provide more details.',
    CURRENT_TIMESTAMP
);


-- ==========================================================
-- 32. PRIORITY DECISIONS
-- ==========================================================

INSERT INTO priority_decisions
    (appointment_id, priority_score, decision_reason, engine_used, created_at)
VALUES
(
    1,
    90,
    'High priority because the appointment is an approved student request.',
    'AIPriorityEngine_v1',
    CURRENT_TIMESTAMP
),
(
    2,
    60,
    'Medium priority based on the request type and current queue.',
    'AIPriorityEngine_v1',
    CURRENT_TIMESTAMP
);

-- ==========================================================
-- 33. PLACEMENT ANNOUNCEMENTS
-- ==========================================================

INSERT INTO placement_announcements
(
    title,
    company,
    description,
    drive_date,
    registration_deadline,
    registration_link,
    min_cgpa,
    backlogs_allowed,
    target_type,
    department_id,
    section,
    opportunity_type,
    target_student_ids,
    created_by,
    status
)
VALUES
(
    'Software Engineer Intern',
    'Google',
    'Software engineering internship opportunity for eligible students.',
    'Internship',
    '2026-09-15',
    '2026-09-10 23:59:59+05:30',
    'https://careers.google.com',
    8.00,
    0,
    'ALL',
    NULL,
    NULL,
    NULL,
    3,
    'ACTIVE'
),
(
    'Data Analyst',
    'Microsoft',
    'Data analyst opportunity for eligible students.',
    'Full-Time Opportunity',
    '2026-10-05',
    '2026-09-30 17:00:00+05:30',
    'https://careers.microsoft.com',
    7.50,
    1,
    'DEPARTMENT',
    1,
    NULL,
    NULL,
    3,
    'ACTIVE'
),
(
    'Core Engineering',
    'Tata Motors',
    'Core engineering placement opportunity for eligible students.',
    'Placement Drive',
    '2026-11-20',
    '2026-11-10 12:00:00+05:30',
    'https://tatamotors.com/careers',
    7.00,
    2,
    'SECTION',
    2,
    'EE-A',
    NULL,
    3,
    'ACTIVE'
),
(
    'Python Developer',
    'Deloitte',
    'Python development opportunity for students with strong programming skills.',
    'Internship',
    '2026-12-05',
    '2026-11-30 23:59:59+05:30',
    'https://www.deloitte.com/careers',
    7.50,
    0,
    'SELECTED',
    NULL,
    NULL,
    '[7, 8]',
    3,
    'ACTIVE'
);