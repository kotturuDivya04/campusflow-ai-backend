"""
Free Slot Engine tests (pure — runnable with the standard library only).

Covers brief testing items: free-slot calculation, teaching-slot exclusion,
break-slot exclusion, approved-request conflict exclusion, buffer-time conflict,
and Busy-slot exclusion.
"""
import datetime as _dt
import unittest

from app.services.domain import SlotView
from app.services.free_slot_engine import compute_free_slots

# Seeded Period 1..7 (with the natural lunch gap 12:20-13:30 between P4 and P5).
SLOTS = [
    SlotView(1, "Period 1", _dt.time(8, 30), _dt.time(9, 20)),
    SlotView(2, "Period 2", _dt.time(9, 30), _dt.time(10, 20)),
    SlotView(3, "Period 3", _dt.time(10, 30), _dt.time(11, 20)),
    SlotView(4, "Period 4", _dt.time(11, 30), _dt.time(12, 20)),
    SlotView(5, "Period 5", _dt.time(13, 30), _dt.time(14, 20)),
    SlotView(6, "Period 6", _dt.time(14, 30), _dt.time(15, 20)),
    SlotView(7, "Period 7", _dt.time(15, 30), _dt.time(16, 20)),
]


class FreeSlotEngineTests(unittest.TestCase):
    def _ids(self, slots):
        return [s.id for s in slots]

    def test_all_free_when_nothing_occupied(self):
        free = compute_free_slots(
            academic_slots=SLOTS, teaching_slot_ids=[],
            approved_appointment_slot_ids=[], busy_slot_ids=[], buffer_minutes=0,
        )
        self.assertEqual(self._ids(free), [1, 2, 3, 4, 5, 6, 7])

    def test_chronological_order(self):
        shuffled = list(reversed(SLOTS))
        free = compute_free_slots(
            academic_slots=shuffled, teaching_slot_ids=[],
            approved_appointment_slot_ids=[], busy_slot_ids=[], buffer_minutes=0,
        )
        self.assertEqual(self._ids(free), [1, 2, 3, 4, 5, 6, 7])

    def test_teaching_slot_excluded(self):
        free = compute_free_slots(
            academic_slots=SLOTS, teaching_slot_ids=[1, 2],
            approved_appointment_slot_ids=[], busy_slot_ids=[], buffer_minutes=0,
        )
        self.assertNotIn(1, self._ids(free))
        self.assertNotIn(2, self._ids(free))

    def test_break_slot_excluded_by_name(self):
        slots = SLOTS + [SlotView(99, "Lunch Break", _dt.time(12, 20), _dt.time(13, 30))]
        free = compute_free_slots(
            academic_slots=slots, teaching_slot_ids=[],
            approved_appointment_slot_ids=[], busy_slot_ids=[], buffer_minutes=0,
        )
        self.assertNotIn(99, self._ids(free))

    def test_approved_appointment_excluded(self):
        free = compute_free_slots(
            academic_slots=SLOTS, teaching_slot_ids=[],
            approved_appointment_slot_ids=[3], busy_slot_ids=[], buffer_minutes=0,
        )
        self.assertNotIn(3, self._ids(free))

    def test_busy_slot_excluded(self):
        free = compute_free_slots(
            academic_slots=SLOTS, teaching_slot_ids=[],
            approved_appointment_slot_ids=[], busy_slot_ids=[6], buffer_minutes=0,
        )
        self.assertNotIn(6, self._ids(free))

    def test_event_slot_excluded_when_supplied(self):
        free = compute_free_slots(
            academic_slots=SLOTS, teaching_slot_ids=[],
            approved_appointment_slot_ids=[], busy_slot_ids=[],
            event_slot_ids=[7], buffer_minutes=0,
        )
        self.assertNotIn(7, self._ids(free))

    def test_buffer_conflict_drops_adjacent_slot(self):
        # Teaching Period 3 (10:30-11:20). With a 15-min buffer, Period 4
        # (11:30-12:20) starts only 10 min after P3 ends -> dropped;
        # Period 2 (9:30-10:20) ends 10 min before P3 starts -> also dropped.
        free = compute_free_slots(
            academic_slots=SLOTS, teaching_slot_ids=[3],
            approved_appointment_slot_ids=[], busy_slot_ids=[], buffer_minutes=15,
        )
        ids = self._ids(free)
        self.assertNotIn(3, ids)   # teaching itself
        self.assertNotIn(4, ids)   # within buffer after P3
        self.assertNotIn(2, ids)   # within buffer before P3
        self.assertIn(1, ids)      # far enough away
        self.assertIn(5, ids)

    def test_zero_buffer_keeps_adjacent(self):
        free = compute_free_slots(
            academic_slots=SLOTS, teaching_slot_ids=[3],
            approved_appointment_slot_ids=[], busy_slot_ids=[], buffer_minutes=0,
        )
        ids = self._ids(free)
        self.assertIn(2, ids)
        self.assertIn(4, ids)


if __name__ == "__main__":
    unittest.main()
