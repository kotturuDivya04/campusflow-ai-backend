"""Venue booking workflows for club events."""
from __future__ import annotations

import datetime as _dt

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.modules.clubs.constants import BOOKING_STATUSES
from app.modules.clubs.models import VenueBooking
from app.modules.clubs.repository import EventRepository, VenueBookingRepository


class VenueManager:
    def __init__(
        self,
        booking_repo: VenueBookingRepository,
        event_repo: EventRepository,
    ) -> None:
        self._bookings = booking_repo
        self._events = event_repo

    def _validate_booking_times(self, start_time: _dt.datetime, end_time: _dt.datetime) -> None:
        if start_time >= end_time:
            raise ValidationFailed("booking start_time must be before end_time")

    def _validate_status(self, status: str | None) -> str:
        resolved = status or "Pending"
        if resolved not in BOOKING_STATUSES:
            raise ValidationFailed(f"invalid booking status '{resolved}'")
        return resolved

    def check_availability(
        self,
        classroom_id: int,
        start_time: _dt.datetime,
        end_time: _dt.datetime,
        exclude_booking_id: int | None = None,
    ) -> bool:
        self._validate_booking_times(start_time, end_time)
        conflicts = self._bookings.overlapping_bookings(
            classroom_id=classroom_id,
            start_time=start_time,
            end_time=end_time,
            exclude_booking_id=exclude_booking_id,
        )
        return len(conflicts) == 0

    def create_booking(self, payload: dict) -> VenueBooking:
        self._validate_booking_times(payload["start_time"], payload["end_time"])
        payload["status"] = self._validate_status(payload.get("status"))
        if not self.check_availability(
            classroom_id=payload["classroom_id"],
            start_time=payload["start_time"],
            end_time=payload["end_time"],
        ):
            raise Conflict("venue already booked for the requested time")
        booking = self._bookings.create(**payload)
        return booking

    def update_booking(self, booking_id: int, payload: dict) -> VenueBooking:
        booking = self._bookings.by_id(booking_id)
        if booking is None:
            raise NotFound(f"booking {booking_id} not found")
        start_time = payload.get("start_time", booking.start_time)
        end_time = payload.get("end_time", booking.end_time)
        self._validate_booking_times(start_time, end_time)
        payload["status"] = self._validate_status(payload.get("status"))
        if not self.check_availability(
            classroom_id=payload.get("classroom_id", booking.classroom_id),
            start_time=start_time,
            end_time=end_time,
            exclude_booking_id=booking.id,
        ):
            raise Conflict("venue already booked for the requested time")
        return self._bookings.update(booking, **payload)

    def cancel_booking(self, booking_id: int) -> None:
        booking = self._bookings.by_id(booking_id)
        if booking is None:
            raise NotFound(f"booking {booking_id} not found")
        booking.status = "Cancelled"
        self._bookings.db.flush()

    def get_booking(self, booking_id: int) -> VenueBooking:
        booking = self._bookings.by_id(booking_id)
        if booking is None:
            raise NotFound(f"booking {booking_id} not found")
        return booking
