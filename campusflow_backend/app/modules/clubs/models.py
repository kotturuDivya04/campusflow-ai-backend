from __future__ import annotations

import datetime as _dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models import Classroom, Faculty, Student, User


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    mentor_faculty_id: Mapped[int | None] = mapped_column(ForeignKey("faculty.id", ondelete="SET NULL"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    mentor: Mapped[Faculty | None] = relationship()
    members: Mapped[list["ClubMember"]] = relationship(back_populates="club", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="club", cascade="all, delete-orphan")
    announcements: Mapped[list["Announcement"]] = relationship(back_populates="club", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "category IN ('Technical','Cultural','Sports','Social','Academic')",
            name="chk_club_category",
        ),
    )


class ClubMember(Base):
    __tablename__ = "club_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'Member'"))
    joined_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    club: Mapped[Club] = relationship(back_populates="members")
    student: Mapped[Student] = relationship()

    __table_args__ = (
        UniqueConstraint("club_id", "student_id", name="uq_club_student"),
        CheckConstraint(
            "role IN ('President','Vice President','Treasurer','Secretary','Core Member','Member')",
            name="chk_club_member_role",
        ),
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    organizing_club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    start_time: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'Pending Approval'"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    club: Mapped[Club] = relationship(back_populates="events")
    registrations: Mapped[list["EventRegistration"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    venue_booking: Mapped["VenueBooking | None"] = relationship(back_populates="event", uselist=False, cascade="all, delete-orphan")
    attendance_records: Mapped[list["EventAttendance"]] = relationship(back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("start_time < end_time", name="chk_event_times"),
    )


class VenueBooking(Base):
    __tablename__ = "venue_bookings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False)
    booked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_time: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Pending'"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    event: Mapped[Event | None] = relationship(back_populates="venue_booking")
    classroom: Mapped[Classroom] = relationship()
    booked_by: Mapped[User] = relationship()

    __table_args__ = (
        CheckConstraint("start_time < end_time", name="chk_booking_times"),
    )


class EventRegistration(Base):
    __tablename__ = "event_registrations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    registered_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Registered'"))

    event: Mapped[Event] = relationship(back_populates="registrations")
    student: Mapped[Student] = relationship()

    __table_args__ = (
        UniqueConstraint("event_id", "student_id", name="uq_event_student_registration"),
        CheckConstraint("status IN ('Registered','Cancelled')", name="chk_registration_status"),
    )


class EventAttendance(Base):
    __tablename__ = "event_attendance"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    marked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    marked_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Present'"))

    event: Mapped[Event] = relationship(back_populates="attendance_records")
    student: Mapped[Student] = relationship()
    marked_by: Mapped[User] = relationship()

    __table_args__ = (
        UniqueConstraint("event_id", "student_id", name="uq_event_attendance"),
        CheckConstraint("status IN ('Present','Absent')", name="chk_attendance_status"),
    )


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'ALL_MEMBERS'"))
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    published_at: Mapped[_dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    club: Mapped[Club] = relationship(back_populates="announcements")
    created_by: Mapped[User] = relationship()

    __table_args__ = (
        CheckConstraint(
            "target IN ('ALL_MEMBERS','PARTICIPANTS','FACULTY','COORDINATORS')",
            name="chk_announcement_target",
        ),
    )
