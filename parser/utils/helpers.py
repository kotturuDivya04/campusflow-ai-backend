import os
from pathlib import Path
from typing import Optional
from utils.logger import logger

def detect_file_type(file_path: str) -> Optional[str]:
    """Detects file type based on file extension and basic structural validation.
    Returns: 'csv', 'excel', 'pdf', or None.
    """
    path = Path(file_path)
    if not path.exists():
        logger.error(f"File not found: {file_path}")
        return None
        
    ext = path.suffix.lower()
    if ext == ".csv":
        return "csv"
    elif ext in (".xlsx", ".xls"):
        return "excel"
    elif ext == ".pdf":
        return "pdf"
        
    logger.warning(f"Unsupported file extension: {ext} for file {file_path}")
    return None

def clean_string(val: any) -> str:
    """Standardizes string values by removing extra whitespace, trailing dots, etc."""
    if val is None or (isinstance(val, float) and val != val):  # nan check
        return ""
    return str(val).strip()

def clean_day_name(day: str) -> str:
    """Normalizes day name to Sentence Case (e.g. 'monday' -> 'Monday')."""
    cleaned = clean_string(day).lower().capitalize()
    # In case of short synonyms (e.g. 'Mon' -> 'Monday')
    mapping = {
        "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
        "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"
    }
    for short, full in mapping.items():
        if cleaned.startswith(short.lower()):
            return full
    return cleaned

def clean_semester_name(sem: str) -> str:
    """Normalizes semester name to standard values ('Fall', 'Spring', 'Summer')."""
    cleaned = clean_string(sem).lower().capitalize()
    if cleaned in ("fall", "autumn"):
        return "Fall"
    elif cleaned in ("spring", "vernally"):
        return "Spring"
    elif cleaned in ("summer", "estival"):
        return "Summer"
    return cleaned
