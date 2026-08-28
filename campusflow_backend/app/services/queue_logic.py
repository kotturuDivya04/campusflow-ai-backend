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
