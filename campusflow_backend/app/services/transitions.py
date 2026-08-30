"""
Status transition tables for the appointment workflow and the operational
queue lifecycle. Adapted from the original backend's transitions module and
retargeted onto the schema-permitted request statuses plus the additive queue
states. An attempt to make a transition not listed here raises IllegalTransition.

requests.status transitions (schema CHECK: Pending/Approved/Rejected/Cancelled/
Rescheduled):

    Pending      -> Approved | Rejected | Cancelled | Rescheduled
    Approved     -> Rescheduled | Cancelled          (post-approval changes)
    Rescheduled  -> Approved | Rejected | Cancelled  (re-decision after reschedule)
    Rejected     -> (terminal)
    Cancelled    -> (terminal)

queue_entries.state transitions:

    WAITING     -> CHECKED_IN | NO_SHOW | WITHDRAWN
    CHECKED_IN  -> READY | IN_PROGRESS | WITHDRAWN
    READY       -> IN_PROGRESS | NO_SHOW | WITHDRAWN
    IN_PROGRESS -> COMPLETED
    COMPLETED / NO_SHOW / WITHDRAWN -> (terminal)
"""
from __future__ import annotations

from app.core.enums import QueueState as Q, RequestStatus as R
from app.core.errors import IllegalTransition

REQUEST_TRANSITIONS: dict[R, frozenset[R]] = {
    R.PENDING: frozenset({R.APPROVED, R.REJECTED, R.CANCELLED, R.RESCHEDULED}),
    R.APPROVED: frozenset({R.RESCHEDULED, R.CANCELLED, R.APPROVED}),
    R.RESCHEDULED: frozenset({R.APPROVED, R.REJECTED, R.CANCELLED}),
    R.REJECTED: frozenset(),
    R.CANCELLED: frozenset(),
}

QUEUE_TRANSITIONS: dict[Q, frozenset[Q]] = {
    Q.WAITING: frozenset({Q.CHECKED_IN, Q.NO_SHOW, Q.WITHDRAWN}),
    Q.CHECKED_IN: frozenset({Q.READY, Q.IN_PROGRESS, Q.WITHDRAWN}),
    Q.READY: frozenset({Q.IN_PROGRESS, Q.NO_SHOW, Q.WITHDRAWN}),
    Q.IN_PROGRESS: frozenset({Q.COMPLETED}),
    Q.COMPLETED: frozenset(),
    Q.NO_SHOW: frozenset(),
    Q.WITHDRAWN: frozenset(),
}


def check_request(old: R, new: R) -> None:
    if new not in REQUEST_TRANSITIONS.get(old, frozenset()):
        raise IllegalTransition(f"request {old.value} -> {new.value}")


def check_queue(old: Q, new: Q) -> None:
    if new not in QUEUE_TRANSITIONS.get(old, frozenset()):
        raise IllegalTransition(f"queue {old.value} -> {new.value}")
