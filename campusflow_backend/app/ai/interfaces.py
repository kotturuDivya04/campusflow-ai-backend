"""
AI boundary — INTERFACES ONLY.

The brief asks for clean interfaces so an AI layer can be added later "without
rewriting the scheduling system", and explicitly forbids AI-driven priority in
this MVP. So:

  * These Protocols are pure function contracts. They accept plain data and
    return plain data — no ORM, no session, no HTTP, no LLM client.
  * The MVP ships deterministic implementations (app/ai/deterministic.py) that
    reuse the same Free Slot Engine output. Swapping in an LLM-backed
    implementation later means writing a new class that satisfies the same
    Protocol; no scheduling code changes.
  * Nothing here influences priority or approval decisions. The AI surface is
    advisory (recommend, explain, summarise) by design.
"""
from __future__ import annotations

import datetime as _dt
from typing import Protocol, Sequence, runtime_checkable

from app.services.domain import SlotView


@runtime_checkable
class SlotRecommender(Protocol):
    """Rank already-free slots for a student. Advisory only."""

    def recommend(
        self, *, free_slots: Sequence[SlotView], date: _dt.date,
        limit: int = 3,
    ) -> list[dict]:
        ...


@runtime_checkable
class ConflictExplainer(Protocol):
    """Explain, in human terms, why a specific slot is unavailable."""

    def explain(
        self, *, slot: SlotView, occupancies: Sequence,
    ) -> str:
        ...


@runtime_checkable
class ScheduleSummarizer(Protocol):
    """Summarise a faculty's day (teaching + appointments) in plain language."""

    def summarize(
        self, *, date: _dt.date, teaching: Sequence[SlotView],
        appointments: Sequence[SlotView], free: Sequence[SlotView],
    ) -> str:
        ...
