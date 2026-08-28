"""Student registration workflows for club events."""
from __future__ import annotations

from datetime import datetime

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.modules.clubs.conflict_engine import student_conflict_exists
from app.modules.clubs.constants import REGISTRATION_STATUSES
from app.modules.clubs.models import Event, EventRegistration
from app.modules.clubs.repository import (
    EventRepository,
    EventRegistrationRepository,
    ClubRepository,
)


class RegistrationManager:
    def __init__(
        self,
        registration_repo: EventRegistrationRepository,
        event_repo: EventRepository,
        club_repo: ClubRepository,
    ) -> None:
        self._registrations = registration_repo
        self._events = event_repo
        self._clubs = club_repo

    def _validate_event(self, event_id: int) -> Event:
        event = self._events.by_id(event_id)
        if event is None:
            raise NotFound(f"event {event_id} not found")
        return event

    def _validate_student(self, student_id: int) -> None:
        if self._registrations.by_id(student_id) is None:
            return

    def _validate_registration_rules(self, event: Event, student_id: int) -> None:
        if event.start_time <= datetime.now(event.start_time.tzinfo):
            raise ValidationFailed("cannot register for past or ongoing events")
        if self._registrations.duplicate_exists(event_id=event.id, student_id=student_id):
            raise Conflict("student already registered for this event")

    def _fetch_registered_ranges(self, student_id: int) -> list[tuple[int, datetime, datetime]]:
        return self._registrations.registered_event_ranges_for_student(student_id)

    def _validate_student_conflict(self, student_id: int, event: Event) -> None:
        ranges = self._fetch_registered_ranges(student_id)
        times = [
            type("R", (), {"start": start, "end": end})() for _id, start, end in ranges
        ]
        if student_conflict_exists(times, event.start_time, event.end_time):
            raise Conflict("student has a schedule conflict with another registered event")

    def create_registration(self, event_id: int, student_id: int) -> EventRegistration:
        event = self._validate_event(event_id)
        self._validate_registration_rules(event, student_id)
        self._validate_student_conflict(student_id, event)
        registration = self._registrations.create(
            event_id=event_id,
            student_id=student_id,
            status="Registered",
        )
        return registration

    def cancel_registration(self, registration_id: int) -> EventRegistration:
        registration = self._registrations.by_id(registration_id)
        if registration is None:
            raise NotFound(f"registration {registration_id} not found")
        return self._registrations.cancel(registration)

    def list_for_event(self, event_id: int, limit: int = 100, offset: int = 0) -> list[EventRegistration]:
        return self._registrations.list_for_event(event_id, limit=limit, offset=offset)

    def list_for_student(self, student_id: int, limit: int = 100, offset: int = 0) -> list[EventRegistration]:
        return self._registrations.list_for_student(student_id, limit=limit, offset=offset)
