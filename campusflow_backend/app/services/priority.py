"""
Deterministic, explainable queue priority — adapted from the original backend's
RuleBasedPriorityProvider (reused per the brief: "Reuse the existing
deterministic priority logic if it can be adapted safely to the new ORM
models"). No AI is involved (brief: "Do not add AI-generated priority decisions
in this MVP").

Ordering rule:
  1. Higher priority weight first (OVERRIDE > CONFIRMED).
  2. Ties broken by booking timestamp, then queue entry id — a strict total
     order, so the outcome never depends on wall-clock timing.

Arrival time is deliberately NOT a priority term; a checked-in student is not
promoted above an earlier booking merely for arriving first. Check-in gates
*eligibility to be called* (handled by the queue service), not priority.
"""
from __future__ import annotations

from typing import Sequence

from app.services.domain import QueueEntryView

PRIORITY_WEIGHTS = {"OVERRIDE": 2, "CONFIRMED": 1}


def priority_weight(entry: QueueEntryView) -> int:
    return PRIORITY_WEIGHTS.get(entry.priority_class, 0)


def priority_score(entry: QueueEntryView) -> int:
    """A single integer surfaced on queue_entries.priority_score."""
    return priority_weight(entry) * 1000


def _tiebreak_key(entry: QueueEntryView):
    ts = entry.booking_ts or entry.entered_at
    return (ts, entry.id)


def order_entries(entries: Sequence[QueueEntryView]) -> list[QueueEntryView]:
    """Return entries in call order (deterministic)."""
    return sorted(entries, key=lambda e: (-priority_weight(e), _tiebreak_key(e)))


def explain_order(entries: Sequence[QueueEntryView]) -> list[dict]:
    out = []
    for rank, e in enumerate(order_entries(entries), start=1):
        out.append({
            "rank": rank,
            "queue_entry_id": e.id,
            "token_number": e.token_number,
            "priority_class": e.priority_class,
            "weight": priority_weight(e),
            "booking_ts": e.booking_ts.isoformat() if e.booking_ts else None,
        })
    return out
