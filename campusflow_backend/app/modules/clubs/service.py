"""Service layer for the Clubs module."""
from __future__ import annotations

import datetime as _dt

from app.core.errors import NotFound, ValidationFailed
from app.notifications.service import NotificationService
from app.modules.clubs.announcement_manager import AnnouncementManager
from app.modules.clubs.attendance_manager import AttendanceManager
from app.modules.clubs.event_manager import EventManager
from app.modules.clubs.registration_manager import RegistrationManager
from app.modules.clubs.repository import (
    AnnouncementRepository,
    ClubRepository,
    EventRepository,
    EventAttendanceRepository,
    EventRegistrationRepository,
    VenueBookingRepository,
)
from app.modules.clubs.utils import pagination_offset
from app.modules.clubs.validators import validate_club_name_uniqueness
from app.modules.clubs.venue_manager import VenueManager
from app.repositories.repositories import TimetableRepository


class ClubService:
    def __init__(
        self,
        club_repo: ClubRepository,
        event_repo: EventRepository,
        booking_repo: VenueBookingRepository,
        registration_repo: EventRegistrationRepository,
        attendance_repo: EventAttendanceRepository,
        announcement_repo: AnnouncementRepository,
        timetable_repo: TimetableRepository,
        notifications: NotificationService,
    ) -> None:
        self._clubs = club_repo
        self._events = EventManager(event_repo, club_repo, booking_repo, timetable_repo)
        self._venue_manager = VenueManager(booking_repo, event_repo)
        self._registrations = RegistrationManager(registration_repo, event_repo, club_repo)
        self._attendance = AttendanceManager(attendance_repo, registration_repo, event_repo)
        self._announcements = AnnouncementManager(announcement_repo, club_repo)
        self._notifications = notifications

    # --- clubs -------------------------------------------------------------
    def create_club(self, payload: dict):
        validate_club_name_uniqueness(self._clubs, payload["name"])
        club = self._clubs.create(**payload)
        return club

    def list_clubs(self, page: int = 1, size: int = 25):
        offset = pagination_offset(page, size)
        return self._clubs.list(limit=size, offset=offset)

    def search_clubs(self, query: str, page: int = 1, size: int = 25):
        offset = pagination_offset(page, size)
        if not query:
            return self._clubs.list(limit=size, offset=offset)
        return self._clubs.search(query=query, limit=size, offset=offset)

    def get_club(self, club_id: int):
        club = self._clubs.by_id(club_id)
        if club is None:
            raise NotFound(f"club {club_id} not found")
        return club

    def update_club(self, club_id: int, payload: dict):
        club = self.get_club(club_id)
        if payload.get("name") and payload["name"] != club.name:
            validate_club_name_uniqueness(self._clubs, payload["name"])
        return self._clubs.update(club, **payload)

    def delete_club(self, club_id: int):
        club = self.get_club(club_id)
        self._clubs.delete(club)

    # --- events ------------------------------------------------------------
    def create_event(self, payload: dict):
        return self._events.create_event(payload)

    def update_event(self, event_id: int, payload: dict):
        return self._events.update_event(event_id, payload)

    def delete_event(self, event_id: int):
        self._events.delete_event(event_id)

    def get_event(self, event_id: int):
        return self._events.get_event(event_id)

    def list_events(self, page: int = 1, size: int = 25):
        offset = pagination_offset(page, size)
        return self._events.list_events(limit=size, offset=offset)

    def list_upcoming_events(self, page: int = 1, size: int = 25):
        offset = pagination_offset(page, size)
        return self._events.list_upcoming(limit=size, offset=offset)

    def list_past_events(self, page: int = 1, size: int = 25):
        offset = pagination_offset(page, size)
        return self._events.list_past(limit=size, offset=offset)

    def search_events(self, q: str | None = None, status: str | None = None, page: int = 1, size: int = 25):
        offset = pagination_offset(page, size)
        return self._events.search_events(q=q, status=status, limit=size, offset=offset)

    # --- registrations ------------------------------------------------------
    def register_student(self, event_id: int, student_id: int):
        registration = self._registrations.create_registration(event_id, student_id)
        self._notifications.notify(
            user_id=student_id,
            event_key="EVENT_INVITATION",
            message=f"You have been registered for event {event_id}.",
        )
        return registration

    def cancel_registration(self, registration_id: int):
        registration = self._registrations.cancel_registration(registration_id)
        return registration

    def registrations_for_event(self, event_id: int, page: int = 1, size: int = 100):
        offset = pagination_offset(page, size)
        return self._registrations.list_for_event(event_id, limit=size, offset=offset)

    def registrations_for_student(self, student_id: int, page: int = 1, size: int = 100):
        offset = pagination_offset(page, size)
        return self._registrations.list_for_student(student_id, limit=size, offset=offset)

    # --- attendance ---------------------------------------------------------
    def mark_attendance(self, payload: dict):
        return self._attendance.mark_attendance(
            event_id=payload["event_id"],
            student_id=payload["student_id"],
            marked_by_user_id=payload["marked_by_user_id"],
            status=payload.get("status", "Present"),
        )

    def bulk_attendance(self, payload: dict):
        return self._attendance.bulk_mark_attendance(
            event_id=payload["event_id"],
            marked_by_user_id=payload["marked_by_user_id"],
            records=payload["records"],
        )

    def attendance_for_event(self, event_id: int, page: int = 1, size: int = 100):
        offset = pagination_offset(page, size)
        return self._attendance.list_for_event(event_id, limit=size, offset=offset)

    def attendance_for_student(self, student_id: int, page: int = 1, size: int = 100):
        offset = pagination_offset(page, size)
        return self._attendance.list_for_student(student_id, limit=size, offset=offset)

    # --- announcements ------------------------------------------------------
    def create_announcement(self, payload: dict):
        return self._announcements.create_announcement(payload)

    def update_announcement(self, announcement_id: int, payload: dict):
        return self._announcements.update_announcement(announcement_id, payload)

    def delete_announcement(self, announcement_id: int):
        self._announcements.delete_announcement(announcement_id)

    def list_announcements(self, page: int = 1, size: int = 50):
        offset = pagination_offset(page, size)
        return self._announcements.list_announcements(limit=size, offset=offset)

    def list_announcements_for_club(self, club_id: int, page: int = 1, size: int = 50):
        offset = pagination_offset(page, size)
        return self._announcements.list_for_club(club_id, limit=size, offset=offset)
