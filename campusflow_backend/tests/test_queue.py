"""
Tests for the PURE live-queue logic (snapshot reconstruction, next-to-call,
token exchange rules). No database involved — these exercise the same functions
QueueService calls after loading rows.
"""
from __future__ import annotations

import datetime as _dt
import unittest

from app.services.domain import QueueEntryView
from app.services.queue_logic import (
    build_snapshot, can_exchange, next_to_call, swap_token_numbers,
)

BASE = _dt.datetime(2026, 3, 2, 9, 0, tzinfo=_dt.timezone.utc)


def entry(eid, token, state="WAITING", *, minutes_offset=0, delay=0,
          priority="CONFIRMED", completed_at=None):
    ts = BASE + _dt.timedelta(minutes=minutes_offset)
    return QueueEntryView(
        id=eid, student_id=100 + eid, token_number=token,
        priority_class=priority, state=state, booking_ts=ts, entered_at=ts,
        effective_minutes=15, delay_minutes=delay, completed_at=completed_at,
    )


class SnapshotTests(unittest.TestCase):
    def test_current_is_the_in_progress_entry(self):
        rows = [entry(1, 1, "IN_PROGRESS"), entry(2, 2), entry(3, 3)]
        snap = build_snapshot(rows)
        self.assertIsNotNone(snap.current)
        self.assertEqual(snap.current.token_number, 1)

    def test_no_current_when_nothing_in_progress(self):
        self.assertIsNone(build_snapshot([entry(1, 1), entry(2, 2)]).current)

    def test_waiting_excludes_terminal_states(self):
        rows = [
            entry(1, 1, "COMPLETED", completed_at=BASE),
            entry(2, 2, "WAITING"),
            entry(3, 3, "CHECKED_IN"),
            entry(4, 4, "NO_SHOW"),
            entry(5, 5, "WITHDRAWN"),
        ]
        snap = build_snapshot(rows)
        self.assertEqual([e.token_number for e in snap.waiting], [2, 3])

    def test_waiting_is_in_priority_order(self):
        rows = [
            entry(1, 1, minutes_offset=0),
            entry(2, 2, minutes_offset=5, priority="OVERRIDE"),
            entry(3, 3, minutes_offset=10),
        ]
        snap = build_snapshot(rows)
        # OVERRIDE outranks earlier bookings; then booking order.
        self.assertEqual([e.id for e in snap.waiting], [2, 1, 3])

    def test_completed_and_no_show_are_grouped(self):
        rows = [
            entry(1, 1, "COMPLETED", completed_at=BASE),
            entry(2, 2, "NO_SHOW"),
        ]
        snap = build_snapshot(rows)
        self.assertEqual([e.id for e in snap.completed], [1])
        self.assertEqual([e.id for e in snap.no_show], [2])

    def test_delayed_lists_only_active_delayed_entries(self):
        rows = [
            entry(1, 1, delay=10),
            entry(2, 2, "COMPLETED", delay=20, completed_at=BASE),
            entry(3, 3, delay=0),
        ]
        snap = build_snapshot(rows)
        self.assertEqual([e.id for e in snap.delayed], [1])

    def test_snapshot_is_derived_only_from_rows(self):
        """Same rows in a different order produce the same snapshot."""
        rows = [entry(1, 1, minutes_offset=0), entry(2, 2, minutes_offset=5)]
        a = build_snapshot(rows)
        b = build_snapshot(list(reversed(rows)))
        self.assertEqual([e.id for e in a.waiting], [e.id for e in b.waiting])


class NextToCallTests(unittest.TestCase):
    def test_only_checked_in_students_can_be_called(self):
        rows = [entry(1, 1, "WAITING", minutes_offset=0),
                entry(2, 2, "CHECKED_IN", minutes_offset=10)]
        nxt = next_to_call(rows)
        self.assertEqual(nxt.id, 2)  # token 1 booked earlier but has not arrived

    def test_none_when_nobody_has_arrived(self):
        self.assertIsNone(next_to_call([entry(1, 1, "WAITING")]))

    def test_priority_wins_among_arrived_students(self):
        rows = [entry(1, 1, "CHECKED_IN", minutes_offset=0),
                entry(2, 2, "CHECKED_IN", minutes_offset=10, priority="OVERRIDE")]
        self.assertEqual(next_to_call(rows).id, 2)


class ExchangeTests(unittest.TestCase):
    def test_two_waiting_students_may_exchange(self):
        ok, _ = can_exchange(entry(1, 1), entry(2, 2))
        self.assertTrue(ok)

    def test_cannot_exchange_with_self(self):
        e = entry(1, 1)
        ok, reason = can_exchange(e, e)
        self.assertFalse(ok)
        self.assertIn("itself", reason)

    def test_cannot_exchange_once_a_meeting_started(self):
        ok, _ = can_exchange(entry(1, 1, "IN_PROGRESS"), entry(2, 2))
        self.assertFalse(ok)

    def test_cannot_exchange_with_completed_entry(self):
        ok, _ = can_exchange(entry(1, 1), entry(2, 2, "COMPLETED"))
        self.assertFalse(ok)

    def test_swap_exchanges_token_numbers(self):
        a, b = entry(1, 3), entry(2, 7)
        swap_token_numbers(a, b)
        self.assertEqual((a.token_number, b.token_number), (7, 3))


if __name__ == "__main__":
    unittest.main()
