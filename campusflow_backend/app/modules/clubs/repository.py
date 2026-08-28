"""Database repositories for the Clubs module."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.clubs.conflict_engine import TimeRange
from app.modules.clubs.models import (
    Announcement,
    Club,
    ClubMember,
    Event,
    EventAttendance,
    EventRegistration,
    VenueBooking,
)


class ClubRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, club_id: int) -> Club | None:
        return self.db.get(Club, club_id)

    def by_name(self, name: str) -> Club | None:
        stmt = select(Club).where(Club.name == name)
        return self.db.scalar(stmt)

    def list(self, limit: int = 50, offset: int = 0) -> list[Club]:
        stmt = select(Club).order_by(Club.name).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def search(self, query: str, limit: int = 50, offset: int = 0) -> list[Club]:
        like = f"%{query}%"
        stmt = select(Club).where(
            or_(Club.name.ilike(like), Club.description.ilike(like), Club.category.ilike(like))
        ).order_by(Club.name).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def create(self, **payload) -> Club:
        club = Club(**payload)
        self.db.add(club)
        self.db.flush()
        return club

    def update(self, club: Club, **payload) -> Club:
        for key, value in payload.items():
            if value is not None:
                setattr(club, key, value)
        self.db.flush()
        return club

    def delete(self, club: Club) -> None:
        self.db.delete(club)
        self.db.flush()


class EventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, event_id: int) -> Event | None:
        return self.db.get(Event, event_id)

    def list(self, limit: int = 50, offset: int = 0) -> list[Event]:
        stmt = select(Event).order_by(Event.start_time).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_upcoming(self, now: datetime, limit: int = 50, offset: int = 0) -> list[Event]:
        stmt = select(Event).where(Event.start_time >= now).order_by(Event.start_time).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_past(self, now: datetime, limit: int = 50, offset: int = 0) -> list[Event]:
        stmt = select(Event).where(Event.end_time < now).order_by(Event.start_time.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def search(self, query: str, status: str | None = None, limit: int = 50, offset: int = 0) -> list[Event]:
        like = f"%{query}%"
        stmt = select(Event).where(
            or_(Event.title.ilike(like), Event.description.ilike(like))
        )
        if status:
            stmt = stmt.where(Event.status == status)
        stmt = stmt.order_by(Event.start_time).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def events_for_club(self, club_id: int, limit: int = 50, offset: int = 0) -> list[Event]:
        stmt = select(Event).where(Event.organizing_club_id == club_id)
        stmt = stmt.order_by(Event.start_time).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def create(self, **payload) -> Event:
        event = Event(**payload)
        self.db.add(event)
        self.db.flush()
        return event

    def update(self, event: Event, **payload) -> Event:
        for key, value in payload.items():
            if value is not None:
                setattr(event, key, value)
        self.db.flush()
        return event

    def delete(self, event: Event) -> None:
        self.db.delete(event)
        self.db.flush()

    def overlapping_events(self, classroom_id: int, start_time: datetime, end_time: datetime, exclude_event_id: int | None = None) -> list[Event]:
        stmt = select(Event).join(VenueBooking, VenueBooking.event_id == Event.id).where(
            and_(
                VenueBooking.classroom_id == classroom_id,
                VenueBooking.start_time < end_time,
                VenueBooking.end_time > start_time,
            )
        )
        if exclude_event_id is not None:
            stmt = stmt.where(Event.id != exclude_event_id)
        return list(self.db.scalars(stmt))

    def club_conflicts(self, club_id: int, start_time: datetime, end_time: datetime, exclude_event_id: int | None = None) -> list[Event]:
        stmt = select(Event).where(
            and_(
                Event.organizing_club_id == club_id,
                Event.start_time < end_time,
                Event.end_time > start_time,
            )
        )
        if exclude_event_id is not None:
            stmt = stmt.where(Event.id != exclude_event_id)
        return list(self.db.scalars(stmt))

    def faculty_conflicts(self, faculty_id: int, start_time: datetime, end_time: datetime, exclude_event_id: int | None = None) -> list[Event]:
        stmt = select(Event).join(Club, Event.organizing_club_id == Club.id).where(
            and_(
                Club.mentor_faculty_id == faculty_id,
                Event.start_time < end_time,
                Event.end_time > start_time,
            )
        )
        if exclude_event_id is not None:
            stmt = stmt.where(Event.id != exclude_event_id)
        return list(self.db.scalars(stmt))


class VenueBookingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, booking_id: int) -> VenueBooking | None:
        return self.db.get(VenueBooking, booking_id)

    def create(self, **payload) -> VenueBooking:
        booking = VenueBooking(**payload)
        self.db.add(booking)
        self.db.flush()
        return booking

    def update(self, booking: VenueBooking, **payload) -> VenueBooking:
        for key, value in payload.items():
            if value is not None:
                setattr(booking, key, value)
        self.db.flush()
        return booking

    def delete(self, booking: VenueBooking) -> None:
        self.db.delete(booking)
        self.db.flush()

    def by_event(self, event_id: int) -> VenueBooking | None:
        stmt = select(VenueBooking).where(VenueBooking.event_id == event_id)
        return self.db.scalar(stmt)

    def overlapping_bookings(self, classroom_id: int, start_time: datetime, end_time: datetime, exclude_booking_id: int | None = None) -> list[VenueBooking]:
        stmt = select(VenueBooking).where(
            and_(
                VenueBooking.classroom_id == classroom_id,
                VenueBooking.start_time < end_time,
                VenueBooking.end_time > start_time,
                VenueBooking.status != "Cancelled",
            )
        )
        if exclude_booking_id is not None:
            stmt = stmt.where(VenueBooking.id != exclude_booking_id)
        return list(self.db.scalars(stmt))


class EventRegistrationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, registration_id: int) -> EventRegistration | None:
        return self.db.get(EventRegistration, registration_id)

    def create(self, **payload) -> EventRegistration:
        registration = EventRegistration(**payload)
        self.db.add(registration)
        self.db.flush()
        return registration

    def cancel(self, registration: EventRegistration) -> EventRegistration:
        registration.status = "Cancelled"
        self.db.flush()
        return registration

    def by_event_and_student(self, event_id: int, student_id: int) -> EventRegistration | None:
        stmt = select(EventRegistration).where(
            and_(
                EventRegistration.event_id == event_id,
                EventRegistration.student_id == student_id,
                EventRegistration.status == "Registered",
            )
        )
        return self.db.scalar(stmt)

    def list_for_event(self, event_id: int, limit: int = 100, offset: int = 0) -> list[EventRegistration]:
        stmt = select(EventRegistration).where(EventRegistration.event_id == event_id).order_by(EventRegistration.registered_at).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_for_student(self, student_id: int, limit: int = 100, offset: int = 0) -> list[EventRegistration]:
        stmt = select(EventRegistration).where(EventRegistration.student_id == student_id).order_by(EventRegistration.registered_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def duplicate_exists(self, event_id: int, student_id: int) -> bool:
        stmt = select(EventRegistration.id).where(
            and_(
                EventRegistration.event_id == event_id,
                EventRegistration.student_id == student_id,
                EventRegistration.status == "Registered",
            )
        )
        return self.db.scalar(stmt) is not None

    def count_for_event(self, event_id: int) -> int:
        stmt = select(func.count()).select_from(EventRegistration).where(
            and_(
                EventRegistration.event_id == event_id,
                EventRegistration.status == "Registered",
            )
        )
        return int(self.db.scalar(stmt) or 0)

    def registered_event_ids_for_student(self, student_id: int) -> set[int]:
        stmt = select(EventRegistration.event_id).where(
            and_(
                EventRegistration.student_id == student_id,
                EventRegistration.status == "Registered",
            )
        )
        return {row[0] for row in self.db.execute(stmt).all()}

    def registered_event_ranges_for_student(
    self, student_id: int
) -> list[tuple[int, datetime, datetime]]:
        stmt = (
        select(Event.id, Event.start_time, Event.end_time)
        .join(
            EventRegistration,
            EventRegistration.event_id == Event.id
        )
        .where(
            EventRegistration.student_id == student_id,
            EventRegistration.status == "Registered",
        )
    )

        return [
        (row[0], row[1], row[2])
        for row in self.db.execute(stmt).all()
    ]
        

    def events_for_student(self, student_id: int, now: datetime | None = None) -> list[EventRegistration]:
        stmt = select(EventRegistration).where(EventRegistration.student_id == student_id)
        if now is not None:
            stmt = stmt.join(Event).where(Event.start_time >= now)
        return list(self.db.scalars(stmt))


class EventAttendanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, attendance_id: int) -> EventAttendance | None:
        return self.db.get(EventAttendance, attendance_id)

    def create(self, **payload) -> EventAttendance:
        attendance = EventAttendance(**payload)
        self.db.add(attendance)
        self.db.flush()
        return attendance

    def by_event_and_student(self, event_id: int, student_id: int) -> EventAttendance | None:
        stmt = select(EventAttendance).where(
            and_(
                EventAttendance.event_id == event_id,
                EventAttendance.student_id == student_id,
            )
        )
        return self.db.scalar(stmt)

    def list_for_event(self, event_id: int, limit: int = 100, offset: int = 0) -> list[EventAttendance]:
        stmt = select(EventAttendance).where(EventAttendance.event_id == event_id).order_by(EventAttendance.marked_at).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_for_student(self, student_id: int, limit: int = 100, offset: int = 0) -> list[EventAttendance]:
        stmt = select(EventAttendance).where(EventAttendance.student_id == student_id).order_by(EventAttendance.marked_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))


class AnnouncementRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, announcement_id: int) -> Announcement | None:
        return self.db.get(Announcement, announcement_id)

    def list(self, limit: int = 50, offset: int = 0) -> list[Announcement]:
        stmt = select(Announcement).order_by(Announcement.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_for_club(self, club_id: int, limit: int = 50, offset: int = 0) -> list[Announcement]:
        stmt = select(Announcement).where(Announcement.club_id == club_id).order_by(Announcement.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def create(self, **payload) -> Announcement:
        announcement = Announcement(**payload)
        self.db.add(announcement)
        self.db.flush()
        return announcement

    def update(self, announcement: Announcement, **payload) -> Announcement:
        for key, value in payload.items():
            if value is not None:
                setattr(announcement, key, value)
        self.db.flush()
        return announcement

    def delete(self, announcement: Announcement) -> None:
        self.db.delete(announcement)
        self.db.flush()
