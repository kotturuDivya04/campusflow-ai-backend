from typing import Any, Optional

class BusinessValidator:
    """Validates row records against business logic (referential lookups, double bookings)."""
    
    def __init__(
        self, 
        departments: dict[str, int],
        faculty: dict[str, int],
        classrooms: dict[str, int],
        subjects: dict[str, int],
        slots: dict[str, int],
        sections: dict[tuple[int, str, int, str], int],
        db_faculty_bookings: Optional[set[tuple]] = None,
        db_classroom_bookings: Optional[set[tuple]] = None,
        db_section_bookings: Optional[set[tuple]] = None
    ):
        self.departments = departments
        self.faculty = faculty
        self.classrooms = classrooms
        self.subjects = subjects
        self.slots = slots
        self.sections = sections
        
        # Database booking caches
        self.db_faculty_bookings = db_faculty_bookings or set()
        self.db_classroom_bookings = db_classroom_bookings or set()
        self.db_section_bookings = db_section_bookings or set()
        
        # In-memory sets to track duplicate slots within the same imported file
        self.seen_faculty_slots = set()     # (faculty_code, day, slot, year, semester)
        self.seen_classroom_slots = set()   # (classroom, day, slot, year, semester)
        self.seen_section_slots = set()     # (dept_code, section, day, slot, year, semester)

    def validate_referential_integrity(self, row: dict[str, Any]) -> tuple[bool, list[str]]:
        """Verifies that all referenced entities exist in database lookups."""
        errors = []
        
        fac_code = row.get("faculty_code")
        dept_code = row.get("department_code")
        subj_code = row.get("subject_code")
        room_num = row.get("classroom_number")
        slot_name = row.get("slot_name")
        sec_name = row.get("section_name")
        year = row.get("academic_year")
        semester = row.get("semester")

        dept_id = self.departments.get(dept_code)
        if not dept_id:
            errors.append(f"Unknown Department: code '{dept_code}' does not exist.")
            
        if fac_code not in self.faculty:
            errors.append(f"Unknown Faculty: code '{fac_code}' does not exist.")
            
        if subj_code not in self.subjects:
            errors.append(f"Unknown Subject: code '{subj_code}' does not exist.")
            
        if room_num not in self.classrooms:
            errors.append(f"Unknown Classroom: number '{room_num}' does not exist.")
            
        if slot_name not in self.slots:
            errors.append(f"Unknown Academic Slot: name '{slot_name}' does not exist.")
            
        if dept_id:
            sec_key = (dept_id, sec_name, int(year), semester)
            if sec_key not in self.sections:
                errors.append(
                    f"Unknown Section: '{sec_name}' does not exist for department '{dept_code}' "
                    f"in semester '{year} {semester}'."
                )
                
        return len(errors) == 0, errors

    def validate_file_duplicates(self, row: dict[str, Any]) -> tuple[bool, list[str]]:
        """Checks for double-booking conflicts within the current import file."""
        errors = []
        
        fac_code = row.get("faculty_code")
        dept_code = row.get("department_code")
        room_num = row.get("classroom_number")
        slot_name = row.get("slot_name")
        sec_name = row.get("section_name")
        day = row.get("day_of_week")
        year = row.get("academic_year")
        semester = row.get("semester")

        fac_key = (fac_code, day, slot_name, year, semester)
        room_key = (room_num, day, slot_name, year, semester)
        sec_key_dup = (dept_code, sec_name, day, slot_name, year, semester)

        if fac_key in self.seen_faculty_slots:
            errors.append(
                f"File Duplicate: Faculty '{fac_code}' is double-booked for slot '{slot_name}' "
                f"on {day} ({year} {semester}) within this file."
            )
        else:
            self.seen_faculty_slots.add(fac_key)

        if room_key in self.seen_classroom_slots:
            errors.append(
                f"File Duplicate: Classroom '{room_num}' is double-booked for slot '{slot_name}' "
                f"on {day} ({year} {semester}) within this file."
            )
        else:
            self.seen_classroom_slots.add(room_key)

        if sec_key_dup in self.seen_section_slots:
            errors.append(
                f"File Duplicate: Section '{sec_name}' ({dept_code}) is scheduled for multiple classes "
                f"in slot '{slot_name}' on {day} ({year} {semester}) within this file."
            )
        else:
            self.seen_section_slots.add(sec_key_dup)

        return len(errors) == 0, errors

    def detect_db_duplicates(self, db_record: dict[str, Any]) -> list[str]:
        """Checks if the proposed database record conflicts with existing bookings in the database."""
        errors = []
        
        sec_id = db_record["section_id"]
        fac_id = db_record["faculty_id"]
        room_id = db_record["classroom_id"]
        slot_id = db_record["academic_slot_id"]
        day = db_record["day_of_week"]
        year = db_record["academic_year"]
        semester = db_record["semester"]

        fac_key = (fac_id, day, slot_id, year, semester)
        room_key = (room_id, day, slot_id, year, semester)
        sec_key = (sec_id, day, slot_id, year, semester)

        if fac_key in self.db_faculty_bookings:
            errors.append(
                f"Database Duplicate: Faculty member is already scheduled for slot ID {slot_id} "
                f"on {day} ({year} {semester})."
            )
            
        if room_key in self.db_classroom_bookings:
            errors.append(
                f"Database Duplicate: Classroom is already booked for slot ID {slot_id} "
                f"on {day} ({year} {semester})."
            )
            
        if sec_key in self.db_section_bookings:
            errors.append(
                f"Database Duplicate: Section is already scheduled for slot ID {slot_id} "
                f"on {day} ({year} {semester})."
            )

        return errors

    def register_successful_booking(self, db_record: dict[str, Any]):
        """Caches a successfully inserted booking in-memory so subsequent rows check against it."""
        sec_id = db_record["section_id"]
        fac_id = db_record["faculty_id"]
        room_id = db_record["classroom_id"]
        slot_id = db_record["academic_slot_id"]
        day = db_record["day_of_week"]
        year = db_record["academic_year"]
        semester = db_record["semester"]

        self.db_faculty_bookings.add((fac_id, day, slot_id, year, semester))
        self.db_classroom_bookings.add((room_id, day, slot_id, year, semester))
        self.db_section_bookings.add((sec_id, day, slot_id, year, semester))
