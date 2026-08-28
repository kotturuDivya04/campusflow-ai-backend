from typing import Any, Optional
from utils.logger import logger

class TimetableMapper:
    """Resolves string values in a normalized row to database IDs using pre-loaded lookup tables."""
    
    def __init__(
        self,
        departments: dict[str, int],  # code -> id
        faculty: dict[str, int],      # faculty_code -> id
        classrooms: dict[str, int],    # room_number -> id
        subjects: dict[str, int],      # code -> id
        slots: dict[str, int],         # slot_name -> id
        sections: dict[tuple[int, str, int, str], int] # (department_id, section_name, academic_year, semester) -> id
    ):
        self.departments = departments
        self.faculty = faculty
        self.classrooms = classrooms
        self.subjects = subjects
        self.slots = slots
        self.sections = sections

    def map_to_db_record(self, record: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Maps standard values of a row to PostgreSQL database foreign key IDs.
        
        Args:
            record: Dictionary containing standard normalized keys.
            
        Returns:
            Dictionary with database foreign keys, ready for INSERT.
            Returns None if mapping fails.
        """
        try:
            # 1. Resolve Department
            dept_code = str(record["department_code"]).strip()
            dept_id = self.departments.get(dept_code)
            if not dept_id:
                raise ValueError(f"Unknown department code: '{dept_code}'")
                
            # 2. Resolve Faculty
            fac_code = str(record["faculty_code"]).strip()
            fac_id = self.faculty.get(fac_code)
            if not fac_id:
                raise ValueError(f"Unknown faculty code: '{fac_code}'")
                
            # 3. Resolve Subject
            subj_code = str(record["subject_code"]).strip()
            subj_id = self.subjects.get(subj_code)
            if not subj_id:
                raise ValueError(f"Unknown subject code: '{subj_code}'")
                
            # 4. Resolve Classroom
            room_num = str(record["classroom_number"]).strip()
            room_id = self.classrooms.get(room_num)
            if not room_id:
                raise ValueError(f"Unknown classroom: '{room_num}'")
                
            # 5. Resolve Slot
            slot_name = str(record["slot_name"]).strip()
            slot_id = self.slots.get(slot_name)
            if not slot_id:
                raise ValueError(f"Unknown academic slot: '{slot_name}'")
                
            # 6. Parse Year & Semester for Section lookup
            section_name = str(record["section_name"]).strip()
            year = int(record["academic_year"])
            semester = str(record["semester"]).strip()
            
            # Lookup Section using composite key: (dept_id, name, year, semester)
            section_key = (dept_id, section_name, year, semester)
            sec_id = self.sections.get(section_key)
            if not sec_id:
                raise ValueError(f"Unknown section '{section_name}' for department ID {dept_id} ({year} {semester})")

            # Return the database record fields
            return {
                "section_id": sec_id,
                "subject_id": subj_id,
                "faculty_id": fac_id,
                "classroom_id": room_id,
                "academic_slot_id": slot_id,
                "day_of_week": str(record["day_of_week"]).strip(),
                "academic_year": year,
                "semester": semester
            }
            
        except Exception as e:
            logger.debug(f"Row mapping failed: {e}")
            raise e
