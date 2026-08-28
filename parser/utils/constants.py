# Normalized Column Names mapping in the parser
NORMALIZED_COLUMNS = [
    "faculty_name",
    "faculty_code",
    "department_code",
    "section_name",
    "subject_code",
    "classroom_number",
    "day_of_week",
    "slot_name",
    "academic_year",
    "semester"
]

# Fuzzy mapping dictionary mapping target normal columns to list of accepted header synonyms
HEADER_SYNONYMS = {
    "faculty_name": [
        "faculty name", "faculty_name", "teacher name", "teacher_name", "staff name", 
        "staff_name", "instructor name", "instructor_name", "teacher", "faculty", "staff", "instructor", "professor"
    ],
    "faculty_code": [
        "faculty code", "faculty_code", "teacher code", "teacher_code", "staff code", 
        "staff_code", "instructor code", "instructor_code", "faculty id", "faculty_id", "teacher id", "staff id"
    ],
    "department_code": [
        "department code", "department_code", "dept code", "dept_code", "department", "dept"
    ],
    "section_name": [
        "section name", "section_name", "class name", "class_name", "section", "class"
    ],
    "subject_code": [
        "subject code", "subject_code", "course code", "course_code", "subject id", "subject_id", "course id", "subject", "course"
    ],
    "classroom_number": [
        "classroom number", "classroom_number", "room number", "room_number", "room", "classroom", "venue", "room no", "room_no"
    ],
    "day_of_week": [
        "day of week", "day_of_week", "weekday", "day"
    ],
    "slot_name": [
        "slot name", "slot_name", "period name", "period_name", "period", "slot", "time slot", "time_slot", "time"
    ],
    "academic_year": [
        "academic year", "academic_year", "year", "session"
    ],
    "semester": [
        "semester", "term"
    ]
}

# Standard Enum values for database compliance
VALID_DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
VALID_SEMESTERS = {"Fall", "Spring", "Summer"}
