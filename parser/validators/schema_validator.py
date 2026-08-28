from pydantic import BaseModel, Field, ValidationError, field_validator
from typing import Any, Optional
from utils.constants import VALID_DAYS, VALID_SEMESTERS
from utils.helpers import clean_day_name, clean_semester_name

class NormalizedTimetableRow(BaseModel):
    """Pydantic model representing a normalized timetable record schema."""
    faculty_name: str = Field(min_length=1)
    faculty_code: str = Field(min_length=1)
    department_code: str = Field(min_length=1)
    section_name: str = Field(min_length=1)
    subject_code: str = Field(min_length=1)
    classroom_number: str = Field(min_length=1)
    day_of_week: str
    slot_name: str = Field(min_length=1)
    academic_year: int = Field(ge=2000, le=2100)
    semester: str

    @field_validator("day_of_week", mode="before")
    @classmethod
    def validate_day(cls, v: Any) -> str:
        """Validates and cleans day of week values."""
        if not v:
            raise ValueError("Day of week cannot be empty")
        cleaned_day = clean_day_name(str(v))
        if cleaned_day not in VALID_DAYS:
            raise ValueError(f"Invalid day: '{v}'. Must be one of {list(VALID_DAYS)}")
        return cleaned_day

    @field_validator("semester", mode="before")
    @classmethod
    def validate_semester(cls, v: Any) -> str:
        """Validates and cleans semester values."""
        if not v:
            raise ValueError("Semester cannot be empty")
        cleaned_sem = clean_semester_name(str(v))
        if cleaned_sem not in VALID_SEMESTERS:
            raise ValueError(f"Invalid semester: '{v}'. Must be one of {list(VALID_SEMESTERS)}")
        return cleaned_sem

class SchemaValidator:
    """Validator class to check if mapped rows conform to NormalizedTimetableRow schema."""
    
    @staticmethod
    def validate_row(row: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[list[str]]]:
        """Validates a single mapped row.
        
        Returns:
            A tuple (validated_row_dict, error_messages_list).
            If validation succeeds, errors list is None.
            If validation fails, validated_row_dict is None.
        """
        try:
            # Let pydantic validate and parse the row
            validated_model = NormalizedTimetableRow(**row)
            return validated_model.model_dump(), None
        except ValidationError as e:
            errors = []
            for err in e.errors():
                loc = ".".join(str(l) for l in err["loc"])
                msg = err["msg"]
                errors.append(f"Schema Error in '{loc}': {msg}")
            return None, errors
