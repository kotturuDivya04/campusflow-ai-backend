# CampusFlow AI - Database Design Documentation

This document provides a comprehensive breakdown of the database design for the **CampusFlow AI** platform. It covers normalization, scalability, entity relationships, and details the specification for every table in the schema.

---

## 1. Normalization (3NF) & Database Scalability

### Third Normal Form (3NF)
The schema strictly complies with the Third Normal Form (3NF) to minimize redundancy and prevent update anomalies:
1. **First Normal Form (1NF):** Every table cell contains only atomic values. There are no repeating groups or comma-separated lists of values (e.g., the `timetable` table stores entries row-wise rather than using array fields for days or slots).
2. **Second Normal Form (2NF):** The schema has no partial key dependencies. In tables with composite primary keys (like bridge tables `user_roles`, `student_subjects`, and `faculty_subjects`), every non-prime attribute is fully functionally dependent on the entire primary key.
3. **Third Normal Form (3NF):** Every non-prime attribute depends only on the primary key, showing no transitive dependencies. For instance, student details map directly to the `students` table, and their department details are referenced via a `department_id` foreign key rather than storing the department name or code directly in the student record.

### Scalability & Performance Strategy
- **Index Optimization:** Indexes are explicitly defined on all foreign keys to prevent full-table scans during standard `JOIN` operations. Conditional indexes (partial indexes) are utilized for tables like `notifications` (indexing only unread messages) and `approvals` (indexing by target IDs) to optimize search latency and reduce index storage sizes.
- **Identity Columns:** All surrogate primary keys utilize the SQL-standard `BIGINT GENERATED ALWAYS AS IDENTITY` clause. This offers better type safety and performance compared to serial types, scaling up to $9.22 \times 10^{18}$ records.
- **Relational Integrity at the DB Level:** Overlaps in the timetable are prevented at insertion time using database-level `UNIQUE` constraints across the combination of resource IDs, slot IDs, day of the week, academic year, and semester. This prevents conflicting entries before they reach the database storage.
- **Audit Logs using JSONB:** The `audit_logs` table stores changes in `old_values` and `new_values` as `JSONB`. This allows developers to log schema changes for any entity in a queryable format without needing separate history tables for every entity, keeping the schema clean and maintainable.

---

## 2. Entity Relationships & Association Rules

### One-to-One (1:1)
- `users` ↔ `faculty`: Each faculty profile is linked to exactly one user account. The `faculty.id` is both the primary key and a foreign key referencing `users(id)`.
- `users` ↔ `students`: Similarly, each student record is linked one-to-one with a user account using the user ID as the primary key.

### One-to-Many (1:N)
- `departments` ↔ `sections`: A department can partition its students into multiple sections.
- `departments` ↔ `subjects`: A department administers many courses/subjects.
- `users` ↔ `tokens`/`notifications`: A single user can have multiple active access tokens and many system notifications.
- `students`/`faculty` ↔ `requests`: A student can submit multiple requests to a faculty member, and a faculty member can receive requests from multiple students.
- `clubs` ↔ `events`: A club can host multiple events over the course of the semester.

### Many-to-Many (N:M) & Bridge Tables
- `users` ↔ `roles` (via `user_roles`): Allows a user to hold multiple roles simultaneously (e.g., a student who is also a `ClubLead`, or a faculty member who is also a `DepartmentAdmin`).
- `students` ↔ `subjects` (via `student_subjects`): Manages student enrollments in different courses.
- `faculty` ↔ `subjects`/`sections` (via `faculty_subjects`): Tracks teaching assignments by mapping a faculty member to specific subjects and sections for a given year and semester.
- `clubs` ↔ `students` (via `club_members`): Manages club memberships and assigns roles (e.g., President, Treasurer) to students.

---

## 3. Comprehensive Table Specifications

---

### 1. `roles`
* **Table Purpose:** Stores user roles to support Role-Based Access Control (RBAC).
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `name` (VARCHAR(50), UNIQUE, NOT NULL) - e.g., 'Student', 'Faculty', 'SuperAdmin'
  * `description` (TEXT, Nullable)
  * `created_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `CURRENT_TIMESTAMP`)
  * `updated_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `CURRENT_TIMESTAMP`)
* **Relationships:** N:M with `users` via `user_roles`.
* **Example Record:** `(1, 'Student', 'Enrolled student attending classes', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 2. `users`
* **Table Purpose:** Central directory of all registered individuals on the platform.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `username` (VARCHAR(50), UNIQUE, NOT NULL)
  * `email` (VARCHAR(100), UNIQUE, NOT NULL)
  * `password_hash` (VARCHAR(255), NOT NULL)
  * `first_name` (VARCHAR(50), NOT NULL)
  * `last_name` (VARCHAR(50), NOT NULL)
  * `phone` (VARCHAR(20), Nullable)
  * `status` (VARCHAR(20), NOT NULL, DEFAULT 'Active') - Check: `IN ('Active', 'Inactive', 'Suspended')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Relationships:** N:M with `roles` via `user_roles`. 1:1 with `faculty` and `students`.
* **Example Record:** `(1, 'sysadmin', 'admin@campusflow.edu', '$2b$12$...', 'System', 'Admin', '+15550100', 'Active', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 3. `user_roles`
* **Table Purpose:** Bridge table mapping users to roles.
* **Attributes & Datatypes:**
  * `user_id` (BIGINT, PRIMARY KEY, REFERENCES `users(id)` ON DELETE CASCADE)
  * `role_id` (BIGINT, PRIMARY KEY, REFERENCES `roles(id)` ON DELETE CASCADE)
  * `created_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `CURRENT_TIMESTAMP`)
* **Example Record:** `(6, 5, '2026-07-16 12:00:00+00')` (User ID 6 is mapped to Role ID 5 - Student)

---

### 4. `departments`
* **Table Purpose:** Represents academic departments (e.g., Computer Science, Electrical Engineering).
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `code` (VARCHAR(20), UNIQUE, NOT NULL) - e.g., 'CS'
  * `name` (VARCHAR(100), NOT NULL)
  * `description` (TEXT, Nullable)
  * `head_faculty_id` (BIGINT, Nullable, REFERENCES `faculty(id)` ON DELETE SET NULL)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Relationships:** 1:N with `sections`, `subjects`.
* **Example Record:** `(1, 'CS', 'Computer Science & Engineering', 'Dept of computing systems', 2, '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 5. `sections`
* **Table Purpose:** Class sections grouped under departments for a given academic term.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `name` (VARCHAR(50), NOT NULL) - e.g., 'Section A'
  * `department_id` (BIGINT, NOT NULL, REFERENCES `departments(id)` ON DELETE CASCADE)
  * `academic_year` (INT, NOT NULL) - Check: `>= 2000`
  * `semester` (VARCHAR(20), NOT NULL) - Check: `IN ('Fall', 'Spring', 'Summer')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Constraints:** Unique combination of `(department_id, name, academic_year, semester)`.
* **Example Record:** `(1, 'CS-A', 1, 2026, 'Fall', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 6. `subjects`
* **Table Purpose:** Academic subjects/courses offered by departments.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `code` (VARCHAR(20), UNIQUE, NOT NULL) - e.g., 'CS-101'
  * `name` (VARCHAR(100), NOT NULL)
  * `description` (TEXT, Nullable)
  * `credits` (INT, NOT NULL) - Check: `>= 0`
  * `department_id` (BIGINT, NOT NULL, REFERENCES `departments(id)` ON DELETE CASCADE)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 'CS-101', 'Introduction to Computing', 'Basic principles', 4, 1, '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 7. `classrooms`
* **Table Purpose:** Campus venues and rooms where classes and events occur.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `room_number` (VARCHAR(50), UNIQUE, NOT NULL) - e.g., 'LH-101'
  * `building` (VARCHAR(100), NOT NULL)
  * `capacity` (INT, NOT NULL) - Check: `> 0`
  * `type` (VARCHAR(50), NOT NULL) - Check: `IN ('Lecture Hall', 'Lab', 'Seminar Room', 'Classroom')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 'LH-101', 'Main Academic Building', 60, 'Lecture Hall', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 8. `faculty`
* **Table Purpose:** Stores profiles of faculty members.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, REFERENCES `users(id)` ON DELETE CASCADE)
  * `faculty_code` (VARCHAR(50), UNIQUE, NOT NULL) - e.g., 'FAC_CS_01'
  * `department_id` (BIGINT, NOT NULL, REFERENCES `departments(id)` ON DELETE RESTRICT)
  * `designation` (VARCHAR(100), NOT NULL) - e.g., 'Associate Professor'
  * `office_location` (VARCHAR(100), Nullable)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(2, 'FAC_CS_01', 1, 'Professor & Head', 'Turing Block, Room 402', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 9. `students`
* **Table Purpose:** Stores profiles of enrolled students.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, REFERENCES `users(id)` ON DELETE CASCADE)
  * `roll_number` (VARCHAR(50), UNIQUE, NOT NULL) - e.g., '2026_CS_001'
  * `department_id` (BIGINT, NOT NULL, REFERENCES `departments(id)` ON DELETE RESTRICT)
  * `section_id` (BIGINT, Nullable, REFERENCES `sections(id)` ON DELETE SET NULL)
  * `admission_year` (INT, NOT NULL) - Check: `>= 2000`
  * `current_semester` (INT, NOT NULL) - Check: `BETWEEN 1 AND 8`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(6, '2026_CS_001', 1, 1, 2026, 1, '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 10. `student_subjects`
* **Table Purpose:** Bridge table mapping students to enrolled subjects.
* **Attributes & Datatypes:**
  * `student_id` (BIGINT, PRIMARY KEY, REFERENCES `students(id)` ON DELETE CASCADE)
  * `subject_id` (BIGINT, PRIMARY KEY, REFERENCES `subjects(id)` ON DELETE CASCADE)
  * `status` (VARCHAR(20), NOT NULL, DEFAULT 'Enrolled') - Check: `IN ('Enrolled', 'Completed', 'Dropped')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(6, 1, 'Enrolled', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 11. `faculty_subjects`
* **Table Purpose:** Bridge table mapping faculty to teaching assignments.
* **Attributes & Datatypes:**
  * `faculty_id` (BIGINT, PRIMARY KEY)
  * `subject_id` (BIGINT, PRIMARY KEY)
  * `section_id` (BIGINT, PRIMARY KEY)
  * `academic_year` (INT, PRIMARY KEY)
  * `semester` (VARCHAR(20), PRIMARY KEY)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(2, 1, 1, 2026, 'Fall', '2026-07-16 12:00:00+00')` (Faculty ID 2 teaches Subject ID 1 to Section ID 1 in Fall 2026)

---

### 12. `academic_slots`
* **Table Purpose:** Defines period structures and standard university slots.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `slot_name` (VARCHAR(50), UNIQUE, NOT NULL) - e.g., 'Period 1'
  * `start_time` (TIME, NOT NULL)
  * `end_time` (TIME, NOT NULL)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Constraints:** Check: `start_time < end_time`
* **Example Record:** `(1, 'Period 1', '08:30:00', '09:20:00', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 13. `timetable`
* **Table Purpose:** Stores scheduled class timings row-wise.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `section_id` (BIGINT, NOT NULL, REFERENCES `sections(id)` ON DELETE CASCADE)
  * `subject_id` (BIGINT, NOT NULL, REFERENCES `subjects(id)` ON DELETE CASCADE)
  * `faculty_id` (BIGINT, NOT NULL, REFERENCES `faculty(id)` ON DELETE CASCADE)
  * `classroom_id` (BIGINT, NOT NULL, REFERENCES `classrooms(id)` ON DELETE CASCADE)
  * `academic_slot_id` (BIGINT, NOT NULL, REFERENCES `academic_slots(id)` ON DELETE RESTRICT)
  * `day_of_week` (VARCHAR(15), NOT NULL) - Check: `IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')`
  * `academic_year` (INT, NOT NULL) - Check: `>= 2000`
  * `semester` (VARCHAR(20), NOT NULL) - Check: `IN ('Fall', 'Spring', 'Summer')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Constraints:**
  * `uq_timetable_classroom`: Prevents classroom double-bookings.
  * `uq_timetable_faculty`: Prevents faculty double-bookings.
  * `uq_timetable_section`: Prevents section double-bookings.
* **Example Record:** `(1, 1, 1, 2, 1, 1, 'Monday', 2026, 'Fall', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 14. `requests`
* **Table Purpose:** Handles student-to-faculty appointment bookings and document requests.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `student_id` (BIGINT, NOT NULL, REFERENCES `students(id)` ON DELETE CASCADE)
  * `faculty_id` (BIGINT, NOT NULL, REFERENCES `faculty(id)` ON DELETE CASCADE)
  * `request_type` (VARCHAR(50), NOT NULL) - Check: `IN ('Appointment', 'Recommendation Letter', 'Project Approval', 'Grade Query', 'Other')`
  * `title` (VARCHAR(100), NOT NULL)
  * `description` (TEXT, NOT NULL)
  * `status` (VARCHAR(20), NOT NULL, DEFAULT 'Pending') - Check: `IN ('Pending', 'Approved', 'Rejected', 'Cancelled', 'Rescheduled')`
  * `scheduled_time` (TIMESTAMPTZ, Nullable)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 6, 2, 'Appointment', 'Discuss Term Project Idea', '...', 'Approved', '2026-07-20 14:00:00+00', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 15. `tokens`
* **Table Purpose:** Stores security tokens (API keys, password reset tokens).
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `user_id` (BIGINT, NOT NULL, REFERENCES `users(id)` ON DELETE CASCADE)
  * `token_value` (VARCHAR(255), UNIQUE, NOT NULL)
  * `token_type` (VARCHAR(50), NOT NULL) - Check: `IN ('API_KEY', 'PASSWORD_RESET', 'EMAIL_VERIFICATION', 'REQUEST_ACCESS')`
  * `expires_at` (TIMESTAMPTZ, NOT NULL)
  * `is_active` (BOOLEAN, NOT NULL, DEFAULT TRUE)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 6, 'apikey_student_alice_xyz123...', 'API_KEY', '2027-01-01 00:00:00+00', TRUE, '2026-07-16 12:00:00+00')`

---

### 16. `notifications`
* **Table Purpose:** Log of sent student and faculty system notifications.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `user_id` (BIGINT, NOT NULL, REFERENCES `users(id)` ON DELETE CASCADE)
  * `title` (VARCHAR(150), NOT NULL)
  * `message` (TEXT, NOT NULL)
  * `type` (VARCHAR(50), NOT NULL) - Check: `IN ('REQUEST_UPDATE', 'EVENT_INVITATION', 'ALERT', 'SYSTEM')`
  * `is_read` (BOOLEAN, NOT NULL, DEFAULT FALSE)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 6, 'Appointment Approved', 'Your meeting with Dr. Turing is approved.', 'REQUEST_UPDATE', FALSE, '2026-07-16 12:00:00+00')`

---

### 17. `clubs`
* **Table Purpose:** Student organizations and technical clubs.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `name` (VARCHAR(100), UNIQUE, NOT NULL)
  * `description` (TEXT, Nullable)
  * `category` (VARCHAR(50), NOT NULL) - Check: `IN ('Technical', 'Cultural', 'Sports', 'Social', 'Academic')`
  * `mentor_faculty_id` (BIGINT, Nullable, REFERENCES `faculty(id)` ON DELETE SET NULL)
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 'Bytes & Logic Club', 'Computer Science club', 'Technical', 2, '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 18. `club_members`
* **Table Purpose:** Membership directory mapping students to clubs.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `club_id` (BIGINT, NOT NULL, REFERENCES `clubs(id)` ON DELETE CASCADE)
  * `student_id` (BIGINT, NOT NULL, REFERENCES `students(id)` ON DELETE CASCADE)
  * `role` (VARCHAR(50), NOT NULL, DEFAULT 'Member') - Check: `IN ('President', 'Vice President', 'Treasurer', 'Secretary', 'Core Member', 'Member')`
  * `joined_at` (TIMESTAMPTZ, NOT NULL)
  * `is_active` (BOOLEAN, NOT NULL, DEFAULT TRUE)
* **Constraints:** Unique `(club_id, student_id)`.
* **Example Record:** `(1, 1, 6, 'President', '2026-07-16 12:00:00+00', TRUE)`

---

### 19. `events`
* **Table Purpose:** Events hosted by student clubs.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `title` (VARCHAR(150), NOT NULL)
  * `description` (TEXT, Nullable)
  * `organizing_club_id` (BIGINT, NOT NULL, REFERENCES `clubs(id)` ON DELETE CASCADE)
  * `start_time` (TIMESTAMPTZ, NOT NULL)
  * `end_time` (TIMESTAMPTZ, NOT NULL)
  * `status` (VARCHAR(30), NOT NULL, DEFAULT 'Pending') - Check: `IN ('Draft', 'Pending Approval', 'Approved', 'Rejected', 'Cancelled')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Constraints:** Check: `start_time < end_time`
* **Example Record:** `(1, 'Autumn AI Hackathon 2026', '...', 1, '2026-10-10 09:00:00+00', '2026-10-11 12:00:00+00', 'Approved', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 20. `venue_bookings`
* **Table Purpose:** Classroom/room booking requests for club events.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `event_id` (BIGINT, Nullable, REFERENCES `events(id)` ON DELETE SET NULL)
  * `classroom_id` (BIGINT, NOT NULL, REFERENCES `classrooms(id)` ON DELETE CASCADE)
  * `booked_by_user_id` (BIGINT, NOT NULL, REFERENCES `users(id)` ON DELETE CASCADE)
  * `start_time` (TIMESTAMPTZ, NOT NULL)
  * `end_time` (TIMESTAMPTZ, NOT NULL)
  * `purpose` (VARCHAR(255), NOT NULL)
  * `status` (VARCHAR(20), NOT NULL, DEFAULT 'Pending') - Check: `IN ('Pending', 'Approved', 'Rejected', 'Cancelled')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Constraints:** Check: `start_time < end_time`
* **Example Record:** `(1, 1, 1, 6, '2026-10-10 08:00:00+00', '2026-10-11 13:00:00+00', 'Hackathon execution', 'Approved', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 21. `faculty_requests`
* **Table Purpose:** Professional coordination requests between faculty members.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `sender_faculty_id` (BIGINT, NOT NULL, REFERENCES `faculty(id)` ON DELETE CASCADE)
  * `receiver_faculty_id` (BIGINT, NOT NULL, REFERENCES `faculty(id)` ON DELETE CASCADE)
  * `request_type` (VARCHAR(50), NOT NULL) - Check: `IN ('Co-teaching', 'Resource Share', 'Duty Exchange', 'Research Collaboration', 'Other')`
  * `title` (VARCHAR(150), NOT NULL)
  * `description` (TEXT, NOT NULL)
  * `status` (VARCHAR(20), NOT NULL, DEFAULT 'Pending') - Check: `IN ('Pending', 'Approved', 'Rejected', 'Cancelled')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 3, 2, 'Co-teaching', 'CS Seminar Lecturing', 'Lambda calculus introduction', 'Approved', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 22. `substitute_requests`
* **Table Purpose:** Temporary substitution requests for specific timetable classes.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `faculty_request_id` (BIGINT, NOT NULL, REFERENCES `faculty_requests(id)` ON DELETE CASCADE)
  * `timetable_id` (BIGINT, NOT NULL, REFERENCES `timetable(id)` ON DELETE CASCADE)
  * `date_of_substitute` (DATE, NOT NULL)
  * `proposed_substitute_faculty_id` (BIGINT, NOT NULL, REFERENCES `faculty(id)` ON DELETE CASCADE)
  * `status` (VARCHAR(20), NOT NULL, DEFAULT 'Pending') - Check: `IN ('Pending', 'Accepted', 'Declined', 'Cancelled')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 1, 3, '2026-09-14', 4, 'Pending', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 23. `department_requests`
* **Table Purpose:** Inter-departmental coordination requests.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `sender_department_id` (BIGINT, NOT NULL, REFERENCES `departments(id)` ON DELETE CASCADE)
  * `receiver_department_id` (BIGINT, NOT NULL, REFERENCES `departments(id)` ON DELETE CASCADE)
  * `request_type` (VARCHAR(50), NOT NULL) - Check: `IN ('Curriculum Change', 'Resource Sharing', 'Interdisciplinary Event', 'Other')`
  * `title` (VARCHAR(150), NOT NULL)
  * `description` (TEXT, NOT NULL)
  * `status` (VARCHAR(20), NOT NULL, DEFAULT 'Pending') - Check: `IN ('Pending', 'Approved', 'Rejected', 'Cancelled')`
  * `created_at` (TIMESTAMPTZ, NOT NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL)
* **Example Record:** `(1, 1, 2, 'Resource Sharing', 'Lab sharing', 'Sim Software request', 'Approved', '2026-07-16 12:00:00+00', '2026-07-16 12:00:00+00')`

---

### 24. `approvals`
* **Table Purpose:** Unified verification records for booking and departmental request workflows.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `department_request_id` (BIGINT, Nullable, REFERENCES `department_requests(id)` ON DELETE CASCADE)
  * `venue_booking_id` (BIGINT, Nullable, REFERENCES `venue_bookings(id)` ON DELETE CASCADE)
  * `event_id` (BIGINT, Nullable, REFERENCES `events(id)` ON DELETE CASCADE)
  * `approver_user_id` (BIGINT, NOT NULL, REFERENCES `users(id)` ON DELETE CASCADE)
  * `status` (VARCHAR(20), NOT NULL) - Check: `IN ('Approved', 'Rejected')`
  * `remarks` (TEXT, Nullable)
  * `action_date` (TIMESTAMPTZ, NOT NULL, DEFAULT `CURRENT_TIMESTAMP`)
* **Constraints:** `chk_single_approval_target` enforces that exactly one reference column must be filled.
* **Example Record:** `(1, 1, NULL, NULL, 4, 'Approved', 'Licenses verified', '2026-07-16 12:05:00+00')`

---

### 25. `chat_history`
* **Table Purpose:** Store user interactions with the AI coordination assistant.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `user_id` (BIGINT, NOT NULL, REFERENCES `users(id)` ON DELETE CASCADE)
  * `session_id` (VARCHAR(100), NOT NULL)
  * `message_role` (VARCHAR(20), NOT NULL) - Check: `IN ('user', 'assistant', 'system')`
  * `message_content` (TEXT, NOT NULL)
  * `created_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `CURRENT_TIMESTAMP`)
* **Example Record:** `(1, 6, 'sess_ab123', 'user', 'Who is Turing?', '2026-07-16 12:00:00+00')`

---

### 26. `ai_logs`
* **Table Purpose:** Logs tokens, latency, prompts, and performance of LLM services.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `user_id` (BIGINT, Nullable, REFERENCES `users(id)` ON DELETE SET NULL)
  * `service_name` (VARCHAR(100), NOT NULL)
  * `prompt` (TEXT, NOT NULL)
  * `response` (TEXT, NOT NULL)
  * `tokens_used` (INT, Nullable) - Check: `>= 0`
  * `latency_ms` (INT, Nullable) - Check: `>= 0`
  * `status` (VARCHAR(20), NOT NULL) - Check: `IN ('Success', 'Failure')`
  * `error_message` (TEXT, Nullable)
  * `created_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `CURRENT_TIMESTAMP`)
* **Example Record:** `(1, 6, 'NLPCoordinator', 'Who is Turing?', '...', 150, 480, 'Success', NULL, '2026-07-16 12:00:00+00')`

---

### 27. `audit_logs`
* **Table Purpose:** Log of all manual or automated database write transactions.
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `user_id` (BIGINT, Nullable, REFERENCES `users(id)` ON DELETE SET NULL)
  * `action` (VARCHAR(100), NOT NULL) - e.g., 'INSERT', 'UPDATE'
  * `table_name` (VARCHAR(100), NOT NULL)
  * `record_id` (BIGINT, NOT NULL)
  * `old_values` (JSONB, Nullable)
  * `new_values` (JSONB, Nullable)
  * `ip_address` (VARCHAR(45), Nullable)
  * `created_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `CURRENT_TIMESTAMP`)
* **Example Record:** `(1, 1, 'INSERT', 'users', 6, NULL, '{"username": "ajones"}', '192.168.1.50', '2026-07-16 12:00:00+00')`

---

### 28. `system_settings`
* **Table Purpose:** System configuration settings (e.g., current semester, maintenance state).
* **Attributes & Datatypes:**
  * `id` (BIGINT, PRIMARY KEY, NOT NULL)
  * `setting_key` (VARCHAR(100), UNIQUE, NOT NULL)
  * `setting_value` (TEXT, NOT NULL)
  * `description` (TEXT, Nullable)
  * `updated_by` (BIGINT, Nullable, REFERENCES `users(id)` ON DELETE SET NULL)
  * `updated_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `CURRENT_TIMESTAMP`)
* **Example Record:** `(1, 'CURRENT_SEMESTER', 'Fall', 'The current active semester', 1, '2026-07-16 12:00:00+00')`
