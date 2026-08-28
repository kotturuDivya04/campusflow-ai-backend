"""Reusable conflict detection for club events and venue bookings."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass


@dataclass(frozen=True)
class TimeRange:
    start: _dt.datetime
    end: _dt.datetime


def overlaps(a_start: _dt.datetime, a_end: _dt.datetime,
             b_start: _dt.datetime, b_end: _dt.datetime) -> bool:
    return a_start < b_end and b_start < a_end


def day_name(dt: _dt.datetime) -> str:
    return dt.strftime("%A")


def venue_conflict_exists(
    bookings: list[tuple[int, TimeRange]],
    classroom_id: int,
    start_time: _dt.datetime,
    end_time: _dt.datetime,
    exclude_booking_id: int | None = None,
) -> bool:
    for booking_id, booked_range in bookings:
        if exclude_booking_id is not None and booking_id == exclude_booking_id:
            continue
        if booked_range.start < end_time and start_time < booked_range.end:
            return True
    return False


def student_conflict_exists(
    registrations: list[TimeRange],
    start_time: _dt.datetime,
    end_time: _dt.datetime,
) -> bool:
    return any(overlaps(start_time, end_time, reg.start, reg.end) for reg in registrations)


def faculty_conflict_exists(
    faculty_events: list[TimeRange],
    start_time: _dt.datetime,
    end_time: _dt.datetime,
) -> bool:
    return any(overlaps(start_time, end_time, evt.start, evt.end) for evt in faculty_events)


def timetable_conflict_exists(
    timetable_entries: list[tuple[str, _dt.time, _dt.time]],
    start_time: _dt.datetime,
    end_time: _dt.datetime,
) -> bool:
    event_day = day_name(start_time)
    for entry_day, entry_start, entry_end in timetable_entries:
        if entry_day != event_day:
            continue
        entry_start_dt = _dt.datetime.combine(start_time.date(), entry_start, tzinfo=start_time.tzinfo)
        entry_end_dt = _dt.datetime.combine(start_time.date(), entry_end, tzinfo=start_time.tzinfo)
        if overlaps(start_time, end_time, entry_start_dt, entry_end_dt):
            return True
    return False
