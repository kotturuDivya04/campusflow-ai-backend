"""
AI Service boundaries for the MVP.

The original brief requested a clean interface boundary for the AI layer so that
it can be fully decoupled from the scheduling engine. 

Per the Frozen Architecture PDF, the AI Priority Engine (System 1) MUST be consumed
by the Meeting Engine to order the queue. The PriorityCalculator protocol establishes
this explicit boundary for calculating ETAs and Queue Positions.
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

from typing import Any

@runtime_checkable
class PriorityCalculator(Protocol):
    """System 1: Calculates appointment queue priority scores and reasoning."""
    async def calculate_priority(self, appointment_details: dict, student_details: dict, faculty_details: dict, category: str, reason: str, requested_duration: int) -> Any:
        ...
