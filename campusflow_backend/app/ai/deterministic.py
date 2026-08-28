"""
Deterministic implementations of the AI interfaces.

These are rule-based and fully explainable — no model calls, no randomness, no
network. They exist so the API surface is real and testable today, and so the
seam is proven: replacing any of these with an LLM-backed class requires no
change to the scheduling code that consumes them.
"""
from __future__ import annotations

import datetime as _dt
from typing import Sequence

from app.services.domain import SlotView
from app.services.free_slot_engine import explain_unavailable


class DeterministicSlotRecommender:
    """
    Ranks free slots by a simple, stated heuristic:
      1. earlier in the day first (students generally prefer the first opening);
      2. ties broken by slot id for a strict total order.
    The score is normalised to [0, 1] purely for presentation.
    """

    def recommend(self, *, free_slots: Sequence[SlotView], date: _dt.date,
                  limit: int = 3) -> list[dict]:
        ordered = sorted(free_slots, key=lambda s: (s.start_min(), s.id))
        n = max(1, len(ordered))
        out = []
        for rank, s in enumerate(ordered[:limit]):
            out.append({
                "slot_id": s.id,
                "slot_name": s.slot_name,
                "date": date,
                "score": round(1.0 - (rank / n), 3),
                "rationale": (f"'{s.slot_name}' is free and is the "
                              f"{_ordinal(rank + 1)} available opening that day."),
            })
        return out


class DeterministicConflictExplainer:
    def explain(self, *, slot: SlotView, occupancies: Sequence) -> str:
        return explain_unavailable(slot=slot, occupancies=occupancies)


class DeterministicScheduleSummarizer:
    def summarize(self, *, date: _dt.date, teaching: Sequence[SlotView],
                  appointments: Sequence[SlotView], free: Sequence[SlotView]) -> str:
        parts = [f"On {date.isoformat()} you have {len(teaching)} teaching slot(s)"]
        if teaching:
            parts[-1] += " (" + ", ".join(s.slot_name for s in teaching) + ")"
        parts.append(f"{len(appointments)} approved appointment slot(s)")
        parts.append(f"and {len(free)} slot(s) still free")
        if free:
            parts[-1] += " (" + ", ".join(s.slot_name for s in free) + ")"
        return ", ".join(parts) + "."


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
