"""
Pure live-queue logic.

Everything here operates on QueueEntryView dataclasses only — no ORM, no
session — so the queue reconstruction rules can be unit-tested with the standard
library. QueueService (repository-backed) loads rows, calls these functions, and
persists the results.

Reconstruction rule (brief: "reconstruct queue state from the database rather
than depending on in-memory state"): the live queue for a (faculty, date, slot)
is derived entirely from the persisted queue_entries rows for that session —
their state, timestamps, delay and priority — never from process memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.core.enums import QueueState
from app.services.priority import order_entries

_ACTIVE = {QueueState.WAITING.value, QueueState.CHECKED_IN.value, QueueState.READY.value}


@dataclass
class QueueSnapshot:
    """A derived, read-only view of one (faculty, date, slot) session."""
    current: object | None = None                 # QueueEntryView in progress
    waiting: list = None                          # ordered, not yet met
    completed: list = None
    no_show: list = None
    delayed: list = None

    def __post_init__(self) -> None:
        self.waiting = self.waiting or []
        self.completed = self.completed or []
        self.no_show = self.no_show or []
        self.delayed = self.delayed or []


def build_snapshot(entries: Sequence) -> QueueSnapshot:
    """Derive the live queue snapshot from persisted entries."""
    current = next(
        (e for e in entries if e.state == QueueState.IN_PROGRESS.value), None)
    waiting = order_entries([e for e in entries if e.state in _ACTIVE])
    completed = sorted(
        [e for e in entries if e.state == QueueState.COMPLETED.value],
        key=lambda e: (e.completed_at or e.entered_at, e.id))
    no_show = [e for e in entries if e.state == QueueState.NO_SHOW.value]
    delayed = [e for e in entries if e.delay_minutes > 0
               and e.state not in {QueueState.COMPLETED.value,
                                   QueueState.WITHDRAWN.value}]
    return QueueSnapshot(current=current, waiting=waiting,
                         completed=completed, no_show=no_show, delayed=delayed)


def next_to_call(entries: Sequence):
    """
    The entry that should be called next: highest-priority student who has
    physically checked in. A WAITING (not arrived) student is never called,
    which is what makes check-in meaningful without making it a priority term.
    """
    callable_states = {QueueState.CHECKED_IN.value, QueueState.READY.value}
    candidates = [e for e in entries if e.state in callable_states]
    ordered = order_entries(candidates)
    return ordered[0] if ordered else None


def can_exchange(a, b) -> tuple[bool, str]:
    """
    Two students may swap queue positions only if both are still waiting to be
    seen and neither meeting has begun. Returns (ok, reason).
    """
    if a.id == b.id:
        return False, "cannot exchange a token with itself"
    for e in (a, b):
        if e.state not in _ACTIVE:
            return False, f"token #{e.token_number} is no longer exchangeable"
    return True, "ok"


def swap_token_numbers(a, b) -> None:
    """In-place swap of the two token numbers (pure; caller persists)."""
    a.token_number, b.token_number = b.token_number, a.token_number


# --- FINAL_DIVYA swap-request cascade candidate selection -------------------
# Adapted to this tree's actual SwapRequest model: candidates are QueueEntry
# rows (or lightweight equivalents) with .id, .priority_score, .student_id.
# "Eligible" here means: a WAITING entry, on the same (faculty, date), with a
# LOWER priority_score than the AI-boosted requester - i.e. the same
# comparison student.py's reevaluate_queue_entry already used for the first
# proposal. This pure function is what decide-on-decline uses to pick the
# NEXT candidate, excluding the requester and anyone already asked.

def order_affected_by_busy(entries):
    """
    Deterministic processing order for the students displaced by a single
    Faculty BUSY/UNAVAILABLE action on one period: highest priority_score
    first, tied students broken by entry.created_at (set once at original
    approval, never touched by later reschedules) then id - i.e. the
    earliest-approved request among equal-priority students always gets
    first pick of a replacement slot. Mirrors the (booking_ts, id) FCFS
    tiebreak convention used by order_entries() for the live queue, applied
    here to the reschedule-cascade's own processing order. Pure: entries only
    need .priority_score, .created_at, .id attributes.
    """
    return sorted(entries, key=lambda e: (-e.priority_score, e.created_at, e.id))


def is_ahead_in_session(candidate_slot_start, candidate_token_number,
                        requester_slot_start, requester_token_number) -> bool:
    """
    True only when `candidate` genuinely holds an EARLIER appointment than
    the requester on the same day - i.e. is actually eligible to be asked
    to give up their earlier slot in a swap. Ordering is by academic-period
    START TIME first (periods are chronological by clock time, NOT by
    academic_slot_id, which is just an arbitrary primary key), then by
    token_number within the same period. A candidate in a LATER period, or
    a later token within the SAME period, is never "ahead" - swapping with
    them would not get the urgent requester an earlier appointment, so they
    must never be offered as a swap target.
    """
    if candidate_slot_start != requester_slot_start:
        return candidate_slot_start < requester_slot_start
    return candidate_token_number < requester_token_number


def exclude_pending_targets(candidates, pending_target_ids: set):
    """
    Candidates who already hold an outstanding PENDING SwapRequest as the
    TARGET (from ANY requester, not just this cascade) must not be offered
    a second, simultaneous swap decision until the first one resolves -
    a student should never be juggling two conflicting swap proposals for
    the same queue entry at once. This guards requirement 11 (no
    duplicate/conflicting proposals).
    """
    return [c for c in candidates if c.id not in pending_target_ids]


def select_next_swap_candidate(candidates, *, requester_priority_score: int,
                               already_asked_ids: set):
    """
    From a list of same-session active QueueEntry-like objects (already
    filtered to the right faculty/date/state by the caller's DB query),
    return the highest-priority-score-yet-still-lower-than-requester
    candidate not already asked - i.e. "first eligible acceptor" order,
    highest remaining priority first (mirrors the DB query's own
     intent, but pure/testable). Returns
    None when nothing eligible remains.
    """
    eligible = [
        c for c in candidates
        if c.id not in already_asked_ids
        and c.priority_score < requester_priority_score
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda c: (c.priority_score, -c.id))
