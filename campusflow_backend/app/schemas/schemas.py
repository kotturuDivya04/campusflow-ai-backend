"""
Pydantic v2 schemas — the API's request/response contracts. Deliberately kept
separate from the SQLAlchemy ORM models (brief requirement). Grouped in one
module for discoverability; re-exported via app/schemas/__init__.py.
"""
from __future__ import annotations

import datetime as _dt

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


# --- common ---------------------------------------------------------------
class Message(BaseModel):
    detail: str


class ImportSummary(BaseModel):
    inserted: int
    skipped: int
    failed: int
    errors: list[str] = Field(default_factory=list)


# --- auth -----------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    roles: list[str]


class CurrentUser(BaseModel):
    model_config = ORM
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    roles: list[str] = Field(default_factory=list)


# --- users / profiles -----------------------------------------------------
class FacultyProfile(BaseModel):
    model_config = ORM
    id: int
    faculty_code: str
    department_id: int
    designation: str
    office_location: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


class StudentProfile(BaseModel):
    model_config = ORM
    id: int
    roll_number: str
    department_id: int
    section_id: int | None = None
    admission_year: int
    current_semester: int
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


# --- timetable / slots ----------------------------------------------------
class SlotOut(BaseModel):
    model_config = ORM
    id: int
    slot_name: str
    start_time: _dt.time
    end_time: _dt.time


class SlotCreate(BaseModel):
    slot_name: str
    start_time: _dt.time
    end_time: _dt.time


class TimetableRow(BaseModel):
    model_config = ORM
    id: int
    section_id: int
    subject_id: int
    faculty_id: int
    classroom_id: int
    academic_slot_id: int
    day_of_week: str
    academic_year: int
    semester: str


class FreeSlotOut(BaseModel):
    slot_id: int
    slot_name: str
    start_time: _dt.time
    end_time: _dt.time
    date: _dt.date
    available_minutes: int = 50


# --- requests / appointments ---------------------------------------------
class AppointmentCreate(BaseModel):
    faculty_id: int
    academic_slot_id: int
    date: _dt.date
    title: str
    description: str
    request_type: str = "Appointment"
    duration_minutes: int = Field(default=50, ge=5, le=50)


class RequestOut(BaseModel):
    model_config = ORM
    id: int
    student_id: int
    faculty_id: int
    request_type: str
    title: str
    description: str
    status: str
    scheduled_time: _dt.datetime | None = None
    created_at: _dt.datetime | None = None
    student_name: str | None = None


class RejectPayload(BaseModel):
    reason: str


class ReschedulePayload(BaseModel):
    academic_slot_id: int
    date: _dt.date
    note: str | None = None


class BusyPayload(BaseModel):
    academic_slot_id: int
    date: _dt.date
    reason: str | None = None


# --- queue / tokens -------------------------------------------------------
class QueueEntryOut(BaseModel):
    model_config = ORM
    id: int
    request_id: int
    faculty_id: int
    student_id: int
    meeting_date: _dt.date
    academic_slot_id: int
    token_number: int
    priority_class: str
    priority_score: int
    state: str
    checked_in_at: _dt.datetime | None = None
    started_at: _dt.datetime | None = None
    completed_at: _dt.datetime | None = None
    delay_minutes: int = 0
    student_name: str | None = None

class TokenView(BaseModel):
    token_number: int
    state: str
    position_ahead: int
    estimated_wait_minutes: int
    eta_source: str


class DelayPayload(BaseModel):
    minutes: int = Field(ge=1, le=240)


class ExchangePayload(BaseModel):
    other_queue_entry_id: int


class LiveQueueSlot(BaseModel):
    faculty_id: int
    meeting_date: _dt.date
    academic_slot_id: int
    current_token: int | None = None
    waiting_tokens: list[int] = Field(default_factory=list)
    completed_tokens: list[int] = Field(default_factory=list)
    delayed_tokens: list[int] = Field(default_factory=list)
    entries: list[QueueEntryOut] = Field(default_factory=list)


class LiveQueueOut(BaseModel):
    faculty_id: int
    meeting_date: _dt.date
    slots: list[LiveQueueSlot] = Field(default_factory=list)


# --- notifications --------------------------------------------------------
class NotificationOut(BaseModel):
    model_config = ORM
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: _dt.datetime | None = None


# --- admin ----------------------------------------------------------------
class AdminUserCreate(BaseModel):
    """Fields common to both admin-created account types. Mirrors the existing
    `users` table exactly; no new columns are implied."""
    username: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    phone: str | None = Field(default=None, max_length=20)


class StudentCreate(AdminUserCreate):
    """`users` fields + the `students` subtype row."""
    roll_number: str = Field(min_length=1, max_length=50)
    department_id: int
    section_id: int | None = None
    admission_year: int = Field(ge=2000)
    current_semester: int = Field(ge=1, le=8)


class FacultyCreate(AdminUserCreate):
    """`users` fields + the `faculty` subtype row."""
    faculty_code: str = Field(min_length=1, max_length=50)
    department_id: int
    designation: str = Field(min_length=1, max_length=100)
    office_location: str | None = Field(default=None, max_length=100)


class AdminAppointmentOut(BaseModel):
    """
    Read-only Admin projection of an existing `requests` row plus the joined
    student/faculty identity and, where the request has been approved, the
    dated slot carried by its `queue_entries` row.

    There is no `purpose` column in the schema; the existing request_type /
    title / description are returned instead.
    """
    id: int
    student_id: int
    faculty_id: int
    request_type: str
    title: str
    description: str
    status: str
    scheduled_time: _dt.datetime | None = None
    created_at: _dt.datetime | None = None

    student_name: str | None = None
    student_roll_number: str | None = None
    student_email: str | None = None
    faculty_name: str | None = None
    faculty_code: str | None = None
    faculty_email: str | None = None

    # Present only once a queue entry exists (i.e. after approval).
    meeting_date: _dt.date | None = None
    academic_slot_id: int | None = None
    slot_name: str | None = None
    slot_start_time: _dt.time | None = None
    slot_end_time: _dt.time | None = None
    token_number: int | None = None
    queue_state: str | None = None


class AdminNotificationOut(NotificationOut):
    """The existing NotificationOut plus the owning user id, which the Admin
    view needs and the per-user student view does not."""
    user_id: int


class SettingOut(BaseModel):
    model_config = ORM
    setting_key: str
    setting_value: str
    description: str | None = None


class SettingUpdate(BaseModel):
    setting_value: str


# --- AI assistant ---------------------------------------------------------
class SlotRecommendation(BaseModel):
    slot_id: int
    slot_name: str
    date: _dt.date
    score: float
    rationale: str


class ConflictExplanation(BaseModel):
    slot_id: int
    available: bool
    explanation: str
