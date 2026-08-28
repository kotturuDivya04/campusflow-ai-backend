"""
Plain dataclasses used by the pure scheduling/priority/ETA logic.

These deliberately import NOTHING from SQLAlchemy or FastAPI so the decision
core (free-slot engine, priority, ETA, transitions) can be unit-tested with the
standard library alone. Repositories translate ORM rows to and from these.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SlotView:
    """An academic_slots row projected for the engine."""
    id: int
    slot_name: str
    start_time: _dt.time
    end_time: _dt.time

    def start_min(self) -> int:
        return self.start_time.hour * 60 + self.start_time.minute

    def end_min(self) -> int:
        return self.end_time.hour * 60 + self.end_time.minute


@dataclass(frozen=True)
class Occupancy:
    """A reason a slot is occupied, carried through for conflict explanations."""
    slot_id: int
    kind: str            # TEACHING | BREAK | APPOINTMENT | EVENT | BUSY
    detail: str = ""


@dataclass
class FreeSlotResult:
    slot: SlotView
    reason: str = "FREE"


@dataclass
class QueueEntryView:
    """A queue_entries row projected for priority/ETA (pure logic)."""
    id: int
    student_id: int
    token_number: int
    priority_class: str            # CONFIRMED / OVERRIDE / ...
    state: str                     # QueueState value
    booking_ts: _dt.datetime | None
    entered_at: _dt.datetime
    effective_minutes: int
    checked_in_at: _dt.datetime | None = None
    started_at: _dt.datetime | None = None
    completed_at: _dt.datetime | None = None
    delay_minutes: int = 0


@dataclass
class ETAEstimate:
    unavailable: bool = False
    estimated_minutes: int = 0
    position_ahead: int = 0
    calculation_source: str = "DETERMINISTIC_MVP"

    def to_dict(self) -> dict:
        return {
            "unavailable": self.unavailable,
            "estimated_minutes": self.estimated_minutes,
            "position_ahead": self.position_ahead,
            "calculation_source": self.calculation_source,
        }
