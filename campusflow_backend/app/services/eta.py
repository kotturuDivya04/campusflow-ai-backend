"""
Deterministic ETA — adapted from the original DeterministicETAProvider,
simplified to the data the finalized schema (+ queue_entries) actually holds.
Not predictive AI (brief: "The ETA does not need to be predictive AI for the
MVP").

Formula (documented here and in the README)
--------------------------------------------
For a WAITING/CHECKED_IN/READY student S with `ahead` = the students called
before S (per priority order):

    remaining_current = max(0, (started_at + default_meeting) - now)   # if a
                        meeting is IN_PROGRESS; else 0
    ahead_time        = sum(effective_minutes[a] + buffer for a in ahead)
    recorded_delays   = sum(delay_minutes[a] for a in ahead) + delay_of_current
    breaks            = (break_after > 0)
                        ? (len(ahead) // break_after) * break_minutes : 0

    ETA(S) = max(0, remaining_current + ahead_time + recorded_delays + breaks)

Guarantees ETA >= 0 (max(0, ...) at every stage). Uses actual current-meeting
start time when available, recorded delays, default meeting duration and the
number of active tokens ahead — exactly the data sources the brief lists.
"""
from __future__ import annotations

import datetime as _dt
from typing import Sequence

from app.services.domain import ETAEstimate, QueueEntryView
from app.services.priority import order_entries


def estimate_eta(
    *,
    target: QueueEntryView,
    all_active: Sequence[QueueEntryView],
    now: _dt.datetime,
    default_meeting_minutes: int,
    buffer_minutes: int,
    in_progress: QueueEntryView | None = None,
    break_after: int = 0,
    break_minutes: int = 0,
) -> ETAEstimate:
    if target.state not in ("WAITING", "CHECKED_IN", "READY"):
        return ETAEstimate(unavailable=True)

    # Students not yet met, in true call order, excluding the current meeting.
    pending = [
        e for e in all_active
        if e.state in ("WAITING", "CHECKED_IN", "READY")
    ]
    ordered = order_entries(pending)
    try:
        idx = [e.id for e in ordered].index(target.id)
    except ValueError:
        idx = len(ordered)
    ahead = ordered[:idx]

    total = 0

    # Remaining time on the meeting currently in progress.
    if in_progress is not None and in_progress.started_at is not None:
        expected_end = in_progress.started_at + _dt.timedelta(minutes=default_meeting_minutes)
        remaining = int((expected_end - now).total_seconds() // 60)
        total += max(0, remaining)
        total += max(0, in_progress.delay_minutes)

    # Everyone ahead: their meeting length + buffer + any recorded delay.
    for a in ahead:
        dur = a.effective_minutes if a.effective_minutes > 0 else default_meeting_minutes
        total += max(0, dur)
        total += max(0, buffer_minutes)
        total += max(0, a.delay_minutes)

    # Breaks that fall before this student's turn.
    if break_after > 0:
        total += (len(ahead) // break_after) * max(0, break_minutes)

    total = max(0, total)
    return ETAEstimate(
        estimated_minutes=total,
        position_ahead=len(ahead),
        calculation_source="DETERMINISTIC_MVP",
    )
