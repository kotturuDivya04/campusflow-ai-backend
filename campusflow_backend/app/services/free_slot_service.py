"""
FreeSlotService — the repository-backed wrapper around the pure Free Slot
Engine. It resolves every input the engine needs from the database, then calls
`compute_free_slots`. The engine itself stays ORM-free and unit-tested.

Endpoint: GET /faculty/{faculty_id}/free-slots?date=YYYY-MM-DD (see routes).
"""
from __future__ import annotations

import datetime as _dt

from app.core.enums import DAYS_OF_WEEK
from app.repositories.repositories import (
    BusyRepository, RequestRepository, SettingsRepository, SlotRepository,
    TimetableRepository,
)
from app.services.buffer import BufferPolicy
from app.services.domain import SlotView

CURRENT_YEAR_KEY = "CURRENT_ACADEMIC_YEAR"
CURRENT_SEMESTER_KEY = "CURRENT_SEMESTER"


def weekday_name(date: _dt.date) -> str:
    """Monday..Sunday for a date (matches timetable.day_of_week text)."""
    return DAYS_OF_WEEK[date.weekday()]


class FreeSlotService:
    def __init__(
        self,
        *,
        slots: SlotRepository,
        timetable: TimetableRepository,
        requests: RequestRepository,
        busy: BusyRepository,
        settings_repo: SettingsRepository,
    ) -> None:
        self._slots = slots
        self._timetable = timetable
        self._requests = requests
        self._busy = busy
        self._settings = settings_repo
        self._buffer = BufferPolicy(settings_repo)

    def _current_term(self) -> tuple[int, str]:
        year = self._settings.get_int(CURRENT_YEAR_KEY, _dt.date.today().year)
        semester = self._settings.get(CURRENT_SEMESTER_KEY) or "Fall"
        return year, semester

    def compute(
        self,
        *,
        faculty_id: int,
        date: _dt.date,
        event_slot_ids: set[int] | None = None,
    ) -> list[SlotView]:
        from app.services.free_slot_engine import compute_free_slots

        year, semester = self._current_term()
        day = weekday_name(date)

        academic_slots = self._slots.as_views()
        teaching = self._timetable.teaching_slot_ids(faculty_id, day, year, semester)
        busy = self._busy.busy_slot_ids(faculty_id, date)

        # PERIOD != APPOINTMENT: only mark a period fully occupied once its
        # approved count reaches real sub-slot capacity (root-cause fix for
        # the false-409 bug where a second student's request in an
        # already-occupied period was wrongly rejected).
        from app.services.free_slot_engine import full_slots_from_counts

        meeting_minutes = self._buffer.meeting_minutes()
        counts = self._requests.approved_slot_counts_on_date(faculty_id, date)
        approved = full_slots_from_counts(
            academic_slots=academic_slots, approved_counts=counts,
            meeting_minutes=meeting_minutes,
        )

        # EVENT-CONFLICT EXCLUSION IS DEFERRED. The canonical `events` table
        # links only to clubs (events.organizing_club_id) — there is NO
        # faculty-to-event relationship in the schema, and `venue_bookings`
        # links classrooms/users rather than faculty availability. There is
        # therefore no safe, correct way to derive a faculty's event-occupied
        # slots from the finalized schema, so no event slots are excluded. The
        # engine keeps the `event_slot_ids` parameter so the capability can be
        # switched on with zero engine changes once a real relationship exists
        # (see VERIFICATION_REPORT.md / SCHEMA_CAPABILITY_MAP.md).
        events: set[int] = event_slot_ids or set()

        return compute_free_slots(
            academic_slots=academic_slots,
            teaching_slot_ids=teaching,
            approved_appointment_slot_ids=approved,
            busy_slot_ids=busy,
            event_slot_ids=events,
            buffer_minutes=self._buffer.buffer_minutes(),
        )

    def is_free(self, *, faculty_id: int, date: _dt.date, slot_id: int) -> bool:
        return any(s.id == slot_id for s in self.compute(faculty_id=faculty_id, date=date))
