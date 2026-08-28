"""Priority ordering + deterministic ETA tests (pure, stdlib-runnable)."""
import datetime as _dt
import unittest

from app.services.domain import QueueEntryView
from app.services.eta import estimate_eta
from app.services.priority import order_entries, priority_score

UTC = _dt.timezone.utc


def entry(id, token, cls="CONFIRMED", booking_min=0, state="CHECKED_IN",
          minutes=15, delay=0, started=None):
    base = _dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    return QueueEntryView(
        id=id, student_id=100 + id, token_number=token, priority_class=cls,
        state=state, booking_ts=base + _dt.timedelta(minutes=booking_min),
        entered_at=base + _dt.timedelta(minutes=booking_min),
        effective_minutes=minutes, delay_minutes=delay, started_at=started,
    )


class PriorityTests(unittest.TestCase):
    def test_orders_by_booking_ts(self):
        a = entry(1, 1, booking_min=10)
        b = entry(2, 2, booking_min=5)
        c = entry(3, 3, booking_min=20)
        ordered = order_entries([a, b, c])
        self.assertEqual([e.id for e in ordered], [2, 1, 3])

    def test_override_ranks_first(self):
        a = entry(1, 1, booking_min=1)
        b = entry(2, 2, cls="OVERRIDE", booking_min=50)
        ordered = order_entries([a, b])
        self.assertEqual(ordered[0].id, 2)

    def test_priority_score_reflects_class(self):
        self.assertGreater(priority_score(entry(2, 2, cls="OVERRIDE")),
                           priority_score(entry(1, 1, cls="CONFIRMED")))

    def test_deterministic_repeat(self):
        es = [entry(i, i, booking_min=i) for i in range(5, 0, -1)]
        self.assertEqual([e.id for e in order_entries(es)],
                         [e.id for e in order_entries(es)])


class ETATests(unittest.TestCase):
    def test_first_in_line_zero_wait(self):
        now = _dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        a = entry(1, 1, booking_min=1)
        est = estimate_eta(target=a, all_active=[a], now=now,
                           default_meeting_minutes=15, buffer_minutes=5)
        self.assertFalse(est.unavailable)
        self.assertEqual(est.position_ahead, 0)
        self.assertEqual(est.estimated_minutes, 0)

    def test_two_ahead_accumulates(self):
        now = _dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        a = entry(1, 1, booking_min=1, minutes=15)
        b = entry(2, 2, booking_min=2, minutes=15)
        target = entry(3, 3, booking_min=3)
        est = estimate_eta(target=target, all_active=[a, b, target], now=now,
                           default_meeting_minutes=15, buffer_minutes=5)
        # 2 ahead * (15 + 5 buffer) = 40
        self.assertEqual(est.position_ahead, 2)
        self.assertEqual(est.estimated_minutes, 40)

    def test_recorded_delay_added(self):
        now = _dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        a = entry(1, 1, booking_min=1, minutes=15, delay=10)
        target = entry(2, 2, booking_min=2)
        est = estimate_eta(target=target, all_active=[a, target], now=now,
                           default_meeting_minutes=15, buffer_minutes=5)
        # 1 ahead: 15 + 5 + 10 delay = 30
        self.assertEqual(est.estimated_minutes, 30)

    def test_never_negative(self):
        now = _dt.datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        inprog = entry(1, 1, state="IN_PROGRESS",
                       started=_dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC))
        target = entry(2, 2, booking_min=2)
        est = estimate_eta(target=target, all_active=[target], now=now,
                           default_meeting_minutes=15, buffer_minutes=5,
                           in_progress=inprog)
        self.assertGreaterEqual(est.estimated_minutes, 0)

    def test_unavailable_for_completed(self):
        now = _dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        a = entry(1, 1, state="COMPLETED")
        est = estimate_eta(target=a, all_active=[a], now=now,
                           default_meeting_minutes=15, buffer_minutes=5)
        self.assertTrue(est.unavailable)


if __name__ == "__main__":
    unittest.main()
