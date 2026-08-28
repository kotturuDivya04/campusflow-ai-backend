"""Status transition tests (pure, stdlib-runnable)."""
import unittest

from app.core.enums import QueueState as Q, RequestStatus as R
from app.core.errors import IllegalTransition
from app.services.transitions import check_queue, check_request


class RequestTransitionTests(unittest.TestCase):
    def test_pending_to_approved_ok(self):
        check_request(R.PENDING, R.APPROVED)  # no raise

    def test_pending_to_rescheduled_ok(self):
        check_request(R.PENDING, R.RESCHEDULED)

    def test_approved_to_rescheduled_ok(self):
        check_request(R.APPROVED, R.RESCHEDULED)

    def test_rejected_is_terminal(self):
        with self.assertRaises(IllegalTransition):
            check_request(R.REJECTED, R.APPROVED)

    def test_cancelled_is_terminal(self):
        with self.assertRaises(IllegalTransition):
            check_request(R.CANCELLED, R.PENDING)

    def test_approved_cannot_go_back_to_pending(self):
        with self.assertRaises(IllegalTransition):
            check_request(R.APPROVED, R.PENDING)


class QueueTransitionTests(unittest.TestCase):
    def test_full_happy_path(self):
        check_queue(Q.WAITING, Q.CHECKED_IN)
        check_queue(Q.CHECKED_IN, Q.READY)
        check_queue(Q.READY, Q.IN_PROGRESS)
        check_queue(Q.IN_PROGRESS, Q.COMPLETED)

    def test_checkin_direct_to_in_progress(self):
        check_queue(Q.CHECKED_IN, Q.IN_PROGRESS)

    def test_completed_is_terminal(self):
        with self.assertRaises(IllegalTransition):
            check_queue(Q.COMPLETED, Q.IN_PROGRESS)

    def test_cannot_skip_from_waiting_to_in_progress(self):
        with self.assertRaises(IllegalTransition):
            check_queue(Q.WAITING, Q.IN_PROGRESS)


if __name__ == "__main__":
    unittest.main()
