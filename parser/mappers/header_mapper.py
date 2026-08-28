from typing import Any
from utils.constants import HEADER_SYNONYMS, NORMALIZED_COLUMNS
from utils.logger import logger

class HeaderMapper:
    """Fuzzy header mapper that maps user-provided headers to standard internal column names."""
    
    @staticmethod
    def map_headers(raw_record: dict[str, Any]) -> dict[str, Any]:
        """Maps keys in raw_record to normal names based on synonym matching.
        
        Args:
            raw_record: Dictionary with raw keys extracted by parser.
            
        Returns:
            Dictionary mapped to standard NORMALIZED_COLUMNS keys.
        """
        mapped_record = {}
        
        for raw_key, value in raw_record.items():
            if raw_key is None:
                continue
                
            raw_key_clean = str(raw_key).strip().lower()
            mapped = False
            
            # Search for a matching key in HEADER_SYNONYMS
            for standard_col, synonyms in HEADER_SYNONYMS.items():
                if raw_key_clean in synonyms:
                    mapped_record[standard_col] = value
                    mapped = True
                    break
            
            # If no synonyms match, but the raw key matches a standard column directly, map it
            if not mapped:
                # Remove spaces and underscores for exact comparison
                raw_key_flat = raw_key_clean.replace(" ", "").replace("_", "")
                for standard_col in NORMALIZED_COLUMNS:
                    std_col_flat = standard_col.replace("_", "")
                    if raw_key_flat == std_col_flat:
                        mapped_record[standard_col] = value
                        mapped = True
                        break
                        
            # If still not mapped, preserve the raw key in case it's needed or ignore it
            if not mapped:
                mapped_record[raw_key] = value
                
        return mapped_record

    @staticmethod
    def verify_required_headers(mapped_record: dict[str, Any]) -> list[str]:
        """Verifies if all necessary columns exist in the mapped dictionary.
        Returns a list of missing standard column names.
        """
        # For a basic timetable entry, these are required:
        required = [
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
        
        missing = []
        for col in required:
            if col not in mapped_record or mapped_record[col] is None or str(mapped_record[col]).strip() == "":
                missing.append(col)
                
        return missing
