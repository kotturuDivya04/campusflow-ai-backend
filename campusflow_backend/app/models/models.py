"""
SQLAlchemy 2.0 ORM models.

Every column here mirrors the FINALIZED schema (migrations/001_core_schema.sql)
exactly — same table names, BIGINT identity PKs, same columns, same CHECK
domains (mirrored as Python-side validation where useful). Only the two clearly
documented additive tables from migrations/002_mvp_operational.sql
(FacultyBusyBlock, QueueEntry) are new, and they are strictly additive.

Only the subset of canonical tables the MVP actually uses is fully mapped with
relationships; the coordination/club/event/audit tables are mapped enough to be
queryable and to keep foreign keys valid, without building an ERP around them.
"""
from __future__ import annotations

import datetime as _dt

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer,
JSON, String, Text, Time, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# --------------------------------------------------------------------------
# MODULE 1: AUTH & ROLES
# --------------------------------------------------------------------------


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    users: Mapped[list["UserRole"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    faculty: Mapped["Faculty | None"] = relationship(back_populates="user", uselist=False)
    student: Mapped["Student | None"] = relationship(back_populates="user", uselist=False)

    __table_args__ = (
        CheckConstraint("status IN ('Active','Inactive','Suspended')", name="chk_user_status"),
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship(back_populates="users")


# --------------------------------------------------------------------------
# MODULE 2: ACADEMIC INFORMATION
# --------------------------------------------------------------------------


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    head_faculty_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class Section(Base):
    __tablename__ = "sections"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        UniqueConstraint("department_id", "name", "academic_year", "semester", name="uq_department_section"),
    )


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class Classroom(Base):
    __tablename__ = "classrooms"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    room_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    building: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class Faculty(Base):
    __tablename__ = "faculty"
    id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    faculty_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    designation: Mapped[str] = mapped_column(String(100), nullable=False)
    office_location: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    user: Mapped["User"] = relationship(back_populates="faculty")
    department: Mapped["Department"] = relationship()


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    roll_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"))
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False)
    current_semester: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    user: Mapped["User"] = relationship(back_populates="student")
    department: Mapped["Department"] = relationship()
    section: Mapped["Section | None"] = relationship()


class FacultySubject(Base):
    __tablename__ = "faculty_subjects"
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id", ondelete="CASCADE"), primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"), primary_key=True)
    academic_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    semester: Mapped[str] = mapped_column(String(20), primary_key=True)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


# --------------------------------------------------------------------------
# MODULE 3: TIMETABLE
# --------------------------------------------------------------------------


class AcademicSlot(Base):
    __tablename__ = "academic_slots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slot_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    start_time: Mapped[_dt.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[_dt.time] = mapped_column(Time, nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class Timetable(Base):
    __tablename__ = "timetable"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False)
    academic_slot_id: Mapped[int] = mapped_column(ForeignKey("academic_slots.id", ondelete="RESTRICT"), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(15), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        UniqueConstraint("classroom_id", "day_of_week", "academic_slot_id", "academic_year", "semester", name="uq_timetable_classroom"),
        UniqueConstraint("faculty_id", "day_of_week", "academic_slot_id", "academic_year", "semester", name="uq_timetable_faculty"),
        UniqueConstraint("section_id", "day_of_week", "academic_slot_id", "academic_year", "semester", name="uq_timetable_section"),
    )

    slot: Mapped["AcademicSlot"] = relationship()


# --------------------------------------------------------------------------
# MODULE 4: STUDENT <-> FACULTY COORDINATION (CORE MVP)
# --------------------------------------------------------------------------


class Request(Base):
    __tablename__ = "requests"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Pending'"))
    scheduled_time: Mapped[_dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        CheckConstraint("status IN ('Pending','Approved','Rejected','Cancelled','Rescheduled')", name="chk_request_status"),
    )

    queue_entry: Mapped["QueueEntry | None"] = relationship(back_populates="request", uselist=False)
    student: Mapped["Student"] = relationship(foreign_keys=[student_id])

    @property
    def student_name(self) -> str | None:
        if self.student and self.student.user:
            return f"{self.student.user.first_name} {self.student.user.last_name}"
        return None


class Token(Base):
    """Canonical auth/access token table (NOT the queue ticket)."""
    __tablename__ = "tokens"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_value: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    token_type: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        CheckConstraint("token_type IN ('API_KEY','PASSWORD_RESET','EMAIL_VERIFICATION','REQUEST_ACCESS')", name="chk_token_type"),
    )


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        CheckConstraint("type IN ('REQUEST_UPDATE','EVENT_INVITATION','ALERT','SYSTEM')", name="chk_notif_type"),
    )


# --------------------------------------------------------------------------
# MODULE 9 (subset used by MVP): SYSTEM SETTINGS
# --------------------------------------------------------------------------


class SystemSetting(Base):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


# ==========================================================================
# ADDITIVE MVP TABLES (migrations/002_mvp_operational.sql) — documented
# ==========================================================================


class FacultyBusyBlock(Base):
    __tablename__ = "faculty_busy_blocks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False)
    block_date: Mapped[_dt.date] = mapped_column(Date, nullable=False)
    academic_slot_id: Mapped[int] = mapped_column(ForeignKey("academic_slots.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        UniqueConstraint("faculty_id", "block_date", "academic_slot_id", name="uq_faculty_busy"),
    )


class QueueEntry(Base):
    __tablename__ = "queue_entries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, unique=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    meeting_date: Mapped[_dt.date] = mapped_column(Date, nullable=False)
    academic_slot_id: Mapped[int] = mapped_column(ForeignKey("academic_slots.id", ondelete="RESTRICT"), nullable=False)
    token_number: Mapped[int] = mapped_column(Integer, nullable=False)
    access_token_id: Mapped[int | None] = mapped_column(ForeignKey("tokens.id", ondelete="SET NULL"))
    priority_class: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'CONFIRMED'"))
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    state: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'WAITING'"))
    checked_in_at: Mapped[_dt.datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[_dt.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[_dt.datetime | None] = mapped_column(DateTime(timezone=True))
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    exchanged_with_id: Mapped[int | None] = mapped_column(ForeignKey("queue_entries.id", ondelete="SET NULL"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_queue_request"),
        UniqueConstraint("faculty_id", "meeting_date", "academic_slot_id", "token_number", name="uq_queue_token"),
        CheckConstraint("state IN ('WAITING','CHECKED_IN','READY','IN_PROGRESS','COMPLETED','NO_SHOW','WITHDRAWN')", name="chk_queue_state"),
    )

    request: Mapped["Request"] = relationship(back_populates="queue_entry")
    slot: Mapped["AcademicSlot"] = relationship()

    student: Mapped["Student"] = relationship(foreign_keys=[student_id])

    @property
    def student_name(self) -> str | None:
        if self.student and self.student.user:
            return f"{self.student.user.first_name} {self.student.user.last_name}"
        return None

# --------------------------------------------------------------------------
# MODULE 10: PLACEMENT COORDINATION
# --------------------------------------------------------------------------

class PlacementAnnouncement(Base):
    __tablename__ = "placement_announcements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(150), nullable=False)
    opportunity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    drive_date: Mapped[_dt.date | None] = mapped_column(Date)
    registration_deadline: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    registration_link: Mapped[str | None] = mapped_column(String(500))

    min_cgpa: Mapped[float | None] = mapped_column()
    backlogs_allowed: Mapped[int | None] = mapped_column(Integer)

    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ALL'")
    )

    department_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("departments.id", ondelete="SET NULL")
    )

    section: Mapped[str | None] = mapped_column(String(50))
    target_student_ids: Mapped[list[int] | None] = mapped_column(JSON)

    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )

    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'ACTIVE'")
    )   