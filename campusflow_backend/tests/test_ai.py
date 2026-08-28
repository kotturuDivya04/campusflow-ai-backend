"""
Tests for the deterministic AI layer. These also assert that the shipped
implementations satisfy the Protocols in app/ai/interfaces.py — which is the
guarantee that an LLM-backed replacement can be dropped in later without
touching the scheduling code.
"""
from __future__ import annotations

import datetime as _dt
import unittest

from app.ai.deterministic import (
    DeterministicConflictExplainer, DeterministicScheduleSummarizer,
    DeterministicSlotRecommender,
)
from app.ai.interfaces import (
    ConflictExplainer, ScheduleSummarizer, SlotRecommender,
)
from app.services.domain import Occupancy, SlotView

DATE = _dt.date(2026, 3, 2)


def slot(i, name, h, m, eh, em):
    return SlotView(i, name, _dt.time(h, m), _dt.time(eh, em))


SLOTS = [
    slot(1, "Period 1", 9, 0, 9, 50),
    slot(2, "Period 2", 10, 0, 10, 50),
    slot(3, "Period 3", 11, 0, 11, 50),
]


class ProtocolConformanceTests(unittest.TestCase):
    def test_implementations_satisfy_their_protocols(self):
        self.assertIsInstance(DeterministicSlotRecommender(), SlotRecommender)
        self.assertIsInstance(DeterministicConflictExplainer(), ConflictExplainer)
        self.assertIsInstance(DeterministicScheduleSummarizer(), ScheduleSummarizer)


class RecommenderTests(unittest.TestCase):
    def test_recommends_earliest_first(self):
        out = DeterministicSlotRecommender().recommend(
            free_slots=list(reversed(SLOTS)), date=DATE)
        self.assertEqual([r["slot_id"] for r in out], [1, 2, 3])

    def test_respects_limit(self):
        out = DeterministicSlotRecommender().recommend(
            free_slots=SLOTS, date=DATE, limit=2)
        self.assertEqual(len(out), 2)

    def test_is_deterministic(self):
        rec = DeterministicSlotRecommender()
        a = rec.recommend(free_slots=SLOTS, date=DATE)
        b = rec.recommend(free_slots=SLOTS, date=DATE)
        self.assertEqual(a, b)

    def test_empty_input_gives_no_recommendations(self):
        self.assertEqual(
            DeterministicSlotRecommender().recommend(free_slots=[], date=DATE), [])

    def test_every_recommendation_carries_a_rationale(self):
        out = DeterministicSlotRecommender().recommend(free_slots=SLOTS, date=DATE)
        self.assertTrue(all(r["rationale"] for r in out))


class ExplainerTests(unittest.TestCase):
    def test_explains_a_teaching_conflict(self):
        text = DeterministicConflictExplainer().explain(
            slot=SLOTS[0], occupancies=[Occupancy(1, "TEACHING", "CS301")])
        self.assertIn("Period 1", text)
        self.assertIn("class", text)

    def test_reports_availability_when_unoccupied(self):
        text = DeterministicConflictExplainer().explain(slot=SLOTS[0], occupancies=[])
        self.assertIn("available", text)


class SummarizerTests(unittest.TestCase):
    def test_summary_mentions_all_three_counts(self):
        text = DeterministicScheduleSummarizer().summarize(
            date=DATE, teaching=[SLOTS[0]], appointments=[SLOTS[1]], free=[SLOTS[2]])
        self.assertIn("1 teaching slot(s)", text)
        self.assertIn("1 approved appointment slot(s)", text)
        self.assertIn("1 slot(s) still free", text)
        self.assertIn(DATE.isoformat(), text)


if __name__ == "__main__":
    unittest.main()
