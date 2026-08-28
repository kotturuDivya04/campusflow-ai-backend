"""Event management for the Clubs module."""
from __future__ import annotations

import datetime as _dt

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import Timetable
from app.repositories.repositories import TimetableRepository
from app.modules.clubs.conflict_engine import timetable_conflict_exists
from app.modules.clubs.constants import EVENT_STATUSES
from app.modules.clubs.models import Event
from app.modules.clubs.repository import ClubRepository, EventRepository, VenueBookingRepository


class EventManager:
    def __init__(
        self,
        event_repo: EventRepository,
        club_repo: ClubRepository,
        booking_repo: VenueBookingRepository,
        timetable_repo: TimetableRepository,
    ) -> None:
        self._events = event_repo
        self._clubs = club_repo
        self._bookings = booking_repo
        self._timetable = timetable_repo

    def _validate_time_window(self, start_time: _dt.datetime, end_time: _dt.datetime) -> None:
        if start_time >= end_time:
            raise ValidationFailed("event start_time must be before end_time")

    def _validate_status(self, status: str | None) -> str:
        resolved = status or "Draft"
        if resolved not in EVENT_STATUSES:
            raise ValidationFailed(f"invalid event status '{resolved}'")
        return resolved

    def _validate_club(self, club_id: int) -> None:
        if self._clubs.by_id(club_id) is None:
            raise NotFound(f"club {club_id} not found")

    def _validate_faculty_schedule(self, club_id: int, start_time: _dt.datetime, end_time: _dt.datetime) -> None:
        club = self._clubs.by_id(club_id)
        if club is None or club.mentor_faculty_id is None:
            return
        timetable_entries = [
            (row.day_of_week, row.slot.start_time, row.slot.end_time)
            for row in self._timetable.for_faculty(club.mentor_faculty_id)
        ]
        if timetable_conflict_exists(timetable_entries, start_time, end_time):
            raise Conflict("event conflicts with faculty teaching timetable")

    def create_event(self, payload: dict) -> Event:
        self._validate_club(payload["organizing_club_id"])
        self._validate_time_window(payload["start_time"], payload["end_time"])
        payload["status"] = self._validate_status(payload.get("status"))
        self._validate_faculty_schedule(
            payload["organizing_club_id"], payload["start_time"], payload["end_time"],
        )
        event = self._events.create(**payload)
        return event

    def update_event(self, event_id: int, payload: dict) -> Event:
        event = self._events.by_id(event_id)
        if event is None:
            raise NotFound(f"event {event_id} not found")
        if payload.get("start_time") is not None or payload.get("end_time") is not None:
            start_time = payload.get("start_time", event.start_time)
            end_time = payload.get("end_time", event.end_time)
            self._validate_time_window(start_time, end_time)
            self._validate_faculty_schedule(event.organizing_club_id, start_time, end_time)
        if payload.get("status") is not None:
            payload["status"] = self._validate_status(payload["status"])
        event = self._events.update(event, **payload)
        return event

    def delete_event(self, event_id: int) -> None:
        event = self._events.by_id(event_id)
        if event is None:
            raise NotFound(f"event {event_id} not found")
        self._events.delete(event)

    def get_event(self, event_id: int) -> Event:
        event = self._events.by_id(event_id)
        if event is None:
            raise NotFound(f"event {event_id} not found")
        return event

    def list_events(self, limit: int = 50, offset: int = 0) -> list[Event]:
        return self._events.list(limit=limit, offset=offset)

    def list_upcoming(self, now: _dt.datetime | None = None, limit: int = 50, offset: int = 0) -> list[Event]:
        now = now or _dt.datetime.now(_dt.timezone.utc)
        return self._events.list_upcoming(now=now, limit=limit, offset=offset)

    def list_past(self, now: _dt.datetime | None = None, limit: int = 50, offset: int = 0) -> list[Event]:
        now = now or _dt.datetime.now(_dt.timezone.utc)
        return self._events.list_past(now=now, limit=limit, offset=offset)

    def search_events(
        self,
        q: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Event]:
        if q is None and status is None:
            return self._events.list(limit=limit, offset=offset)
        return self._events.search(q or "", status=status, limit=limit, offset=offset)
