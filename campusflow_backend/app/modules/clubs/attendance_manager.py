"""Attendance workflows for club events."""
from __future__ import annotations

from datetime import datetime

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.modules.clubs.constants import ATTENDANCE_STATUSES
from app.modules.clubs.models import Event, EventAttendance
from app.modules.clubs.repository import (
    EventAttendanceRepository,
    EventRegistrationRepository,
    EventRepository,
)


class AttendanceManager:
    def __init__(
        self,
        attendance_repo: EventAttendanceRepository,
        registration_repo: EventRegistrationRepository,
        event_repo: EventRepository,
    ) -> None:
        self._attendance = attendance_repo
        self._registrations = registration_repo
        self._events = event_repo

    def _validate_event(self, event_id: int) -> Event:
        event = self._events.by_id(event_id)
        if event is None:
            raise NotFound(f"event {event_id} not found")
        return event

    def _validate_status(self, status: str) -> str:
        if status not in ATTENDANCE_STATUSES:
            raise ValidationFailed(f"invalid attendance status '{status}'")
        return status

    def _validate_registration(self, event_id: int, student_id: int) -> None:
        registration = self._registrations.by_event_and_student(event_id, student_id)
        if registration is None:
            raise NotFound("student is not registered for this event")

    def _validate_event_started(self, event: Event) -> None:
        if datetime.now(event.start_time.tzinfo) < event.start_time:
            raise ValidationFailed("cannot mark attendance before event start")

    def _validate_no_duplicate(self, event_id: int, student_id: int) -> None:
        if self._attendance.by_event_and_student(event_id, student_id) is not None:
            raise Conflict("attendance for this student has already been recorded")

    def mark_attendance(
        self,
        event_id: int,
        student_id: int,
        marked_by_user_id: int,
        status: str,
    ) -> EventAttendance:
        event = self._validate_event(event_id)
        self._validate_registration(event_id, student_id)
        self._validate_event_started(event)
        self._validate_no_duplicate(event_id, student_id)
        status = self._validate_status(status)
        attendance = self._attendance.create(
            event_id=event_id,
            student_id=student_id,
            marked_by_user_id=marked_by_user_id,
            status=status,
        )
        return attendance

    def bulk_mark_attendance(
        self,
        event_id: int,
        marked_by_user_id: int,
        records: list[dict[str, object]],
    ) -> list[EventAttendance]:
        event = self._validate_event(event_id)
        self._validate_event_started(event)
        seen: set[int] = set()
        results: list[EventAttendance] = []
        for record in records:
            student_id = int(record["student_id"])
            status = self._validate_status(str(record["status"]))
            if student_id in seen:
                raise ValidationFailed(f"duplicate student {student_id} in attendance batch")
            self._validate_registration(event_id, student_id)
            self._validate_no_duplicate(event_id, student_id)
            seen.add(student_id)
            results.append(self._attendance.create(
                event_id=event_id,
                student_id=student_id,
                marked_by_user_id=marked_by_user_id,
                status=status,
            ))
        return results

    def list_for_event(self, event_id: int, limit: int = 100, offset: int = 0) -> list[EventAttendance]:
        return self._attendance.list_for_event(event_id, limit=limit, offset=offset)

    def list_for_student(self, student_id: int, limit: int = 100, offset: int = 0) -> list[EventAttendance]:
        return self._attendance.list_for_student(student_id, limit=limit, offset=offset)
