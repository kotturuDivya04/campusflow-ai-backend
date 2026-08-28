import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.errors import UniqueViolation, ForeignKeyViolation
from config import DATABASE_URL
from utils.logger import logger

class DatabaseService:
    """Manages database connection and provides lookup caching and savepoint-contained PostgreSQL row writes."""
    
    def __init__(self):
        self.conn = None

    def connect(self):
        """Establishes connection to PostgreSQL database."""
        try:
            logger.info("Connecting to PostgreSQL database...")
            self.conn = psycopg2.connect(DATABASE_URL)
            self.conn.autocommit = False  # Enable transaction block manual control
            logger.info("Database connection established successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to the database: {e}")
            raise ConnectionError(f"Database connection error: {e}")

    def close(self):
        """Closes the connection safely."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")

    def fetch_departments(self) -> dict[str, int]:
        """Loads departments into a code -> id mapping dictionary."""
        query = "SELECT code, id FROM departments"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return {r["code"]: r["id"] for r in rows}

    def fetch_faculty(self) -> dict[str, int]:
        """Loads faculty into a faculty_code -> id mapping dictionary."""
        query = "SELECT faculty_code, id FROM faculty"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return {r["faculty_code"]: r["id"] for r in rows}

    def fetch_classrooms(self) -> dict[str, int]:
        """Loads classrooms into a room_number -> id mapping dictionary."""
        query = "SELECT room_number, id FROM classrooms"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return {r["room_number"]: r["id"] for r in rows}

    def fetch_subjects(self) -> dict[str, int]:
        """Loads subjects into a code -> id mapping dictionary."""
        query = "SELECT code, id FROM subjects"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return {r["code"]: r["id"] for r in rows}

    def fetch_slots(self) -> dict[str, int]:
        """Loads academic slots into a slot_name -> id mapping dictionary."""
        query = "SELECT slot_name, id FROM academic_slots"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return {r["slot_name"]: r["id"] for r in rows}

    def fetch_sections(self) -> dict[tuple[int, str, int, str], int]:
        """Loads sections into a composite key -> id mapping dictionary.
        Composite Key: (department_id, section_name, academic_year, semester)
        """
        query = "SELECT id, department_id, name, academic_year, semester FROM sections"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return {
            (r["department_id"], r["name"], r["academic_year"], r["semester"]): r["id"]
            for r in rows
        }

    def fetch_existing_timetable_bookings(self) -> tuple[set[tuple], set[tuple], set[tuple]]:
        """Loads all existing bookings in the database to prevent duplicate slot bookings.
        
        Returns:
            A tuple of sets: (faculty_bookings, classroom_bookings, section_bookings)
            Each element is a set of keys:
            - Faculty: (faculty_id, day_of_week, slot_id, year, semester)
            - Classroom: (classroom_id, day_of_week, slot_id, year, semester)
            - Section: (section_id, day_of_week, slot_id, year, semester)
        """
        query = """
            SELECT faculty_id, classroom_id, section_id, academic_slot_id, 
                   day_of_week, academic_year, semester 
            FROM timetable
        """
        fac_bookings = set()
        room_bookings = set()
        sec_bookings = set()
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
            for r in rows:
                day = r["day_of_week"]
                year = r["academic_year"]
                semester = r["semester"]
                slot_id = r["academic_slot_id"]
                
                fac_bookings.add((r["faculty_id"], day, slot_id, year, semester))
                room_bookings.add((r["classroom_id"], day, slot_id, year, semester))
                sec_bookings.add((r["section_id"], day, slot_id, year, semester))
                
        return fac_bookings, room_bookings, sec_bookings

    def insert_timetable_record(self, record: dict[str, any]) -> tuple[bool, str]:
        """Inserts a single timetable record, using transaction savepoint to isolate failures.
        
        Args:
            record: Dictionary containing database column values.
            
        Returns:
            A tuple (success_boolean, message).
        """
        insert_query = """
            INSERT INTO timetable (
                section_id, subject_id, faculty_id, classroom_id, 
                academic_slot_id, day_of_week, academic_year, semester
            ) VALUES (
                %(section_id)s, %(subject_id)s, %(faculty_id)s, %(classroom_id)s,
                %(academic_slot_id)s, %(day_of_week)s, %(academic_year)s, %(semester)s
            )
        """
        
        try:
            with self.conn.cursor() as cur:
                # Establish savepoint for transactional containment
                cur.execute("SAVEPOINT row_insert_sp")
                cur.execute(insert_query, record)
                cur.execute("RELEASE SAVEPOINT row_insert_sp")
            return True, "Successfully inserted"
            
        except UniqueViolation as e:
            with self.conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT row_insert_sp")
            error_msg = str(e).split("\n")[0]
            logger.debug(f"Database Duplicate Timetable Entry warning: {error_msg}")
            return False, f"Duplicate Timetable Entry: This class booking already exists in the database. Details: {error_msg}"
            
        except ForeignKeyViolation as e:
            with self.conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT row_insert_sp")
            error_msg = str(e).split("\n")[0]
            logger.error(f"Database FK Violation error: {error_msg}")
            return False, f"Database FK Violation: Referenced entity not matched. Details: {error_msg}"
            
        except Exception as e:
            with self.conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT row_insert_sp")
            error_msg = str(e).split("\n")[0]
            logger.error(f"Database execution error: {error_msg}")
            return False, f"Database Error: {error_msg}"

    def commit(self):
        """Commits active transaction block."""
        if self.conn:
            self.conn.commit()
            logger.info("Transaction committed successfully.")

    def rollback(self):
        """Rolls back active transaction block."""
        if self.conn:
            self.conn.rollback()
            logger.info("Transaction rolled back.")
