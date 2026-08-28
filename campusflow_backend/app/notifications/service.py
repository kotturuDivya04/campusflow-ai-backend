"""
Notifications.

The canonical `notifications` table only permits four `type` values
(REQUEST_UPDATE, EVENT_INVITATION, ALERT, SYSTEM). The brief asks for a much
longer list of *events* (request submitted, approval, rejection, busy,
reschedule, token generated, queue update, approaching meeting, delay, token
exchange, completion).

We therefore keep an application-level EVENT catalogue that maps each business
event onto one of the four permitted schema types, plus a human title/message.
Nothing here invents a new enum value — the richness lives in title/message
while `type` stays inside the CHECK constraint.

Email delivery stays behind EmailStub (a development no-op) so a real provider
can be dropped in later without touching callers (brief: "Email delivery may
remain behind a service interface or development stub").
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import NotificationType
from app.repositories.repositories import NotificationRepository


@dataclass(frozen=True)
class NotificationEvent:
    key: str
    type: NotificationType
    title: str


# Business event -> (schema type, default title). Message is filled per-call.
EVENTS: dict[str, NotificationEvent] = {
    "REQUEST_SUBMITTED": NotificationEvent(
        "REQUEST_SUBMITTED", NotificationType.REQUEST_UPDATE, "New appointment request"),
    "REQUEST_APPROVED": NotificationEvent(
        "REQUEST_APPROVED", NotificationType.REQUEST_UPDATE, "Appointment approved"),
    "REQUEST_REJECTED": NotificationEvent(
        "REQUEST_REJECTED", NotificationType.REQUEST_UPDATE, "Appointment rejected"),
    "FACULTY_BUSY": NotificationEvent(
        "FACULTY_BUSY", NotificationType.ALERT, "Slot marked busy"),
    "REQUEST_RESCHEDULED": NotificationEvent(
        "REQUEST_RESCHEDULED", NotificationType.REQUEST_UPDATE, "Appointment rescheduled"),
    "TOKEN_GENERATED": NotificationEvent(
        "TOKEN_GENERATED", NotificationType.REQUEST_UPDATE, "Queue token generated"),
    "QUEUE_UPDATE": NotificationEvent(
        "QUEUE_UPDATE", NotificationType.SYSTEM, "Queue update"),
    "MEETING_APPROACHING": NotificationEvent(
        "MEETING_APPROACHING", NotificationType.ALERT, "Your meeting is approaching"),
    "DELAY_RECORDED": NotificationEvent(
        "DELAY_RECORDED", NotificationType.ALERT, "Delay recorded"),
    "TOKEN_EXCHANGE": NotificationEvent(
        "TOKEN_EXCHANGE", NotificationType.REQUEST_UPDATE, "Token exchange result"),
    "MEETING_COMPLETED": NotificationEvent(
        "MEETING_COMPLETED", NotificationType.REQUEST_UPDATE, "Meeting completed"),
    "MEETING_STARTED": NotificationEvent(
        "MEETING_STARTED", NotificationType.REQUEST_UPDATE, "Meeting started"),
}


class EmailStub:
    """Development stub. Swap for an SMTP/provider implementation later."""

    def send(self, *, to_user_id: int, subject: str, body: str) -> None:  # noqa: D401
        # Intentionally a no-op in the MVP; kept behind an interface so a real
        # provider can be introduced without changing NotificationService.
        return None


class NotificationService:
    def __init__(self, repo: NotificationRepository, email: EmailStub | None = None) -> None:
        self._repo = repo
        self._email = email or EmailStub()

    def notify(self, *, user_id: int, event_key: str, message: str,
               title: str | None = None, send_email: bool = False):
        """Create an in-app notification for a business event."""
        event = EVENTS.get(event_key)
        if event is None:  # defensive: unknown events degrade to SYSTEM
            ntype = NotificationType.SYSTEM
            resolved_title = title or "Notification"
        else:
            ntype = event.type
            resolved_title = title or event.title
        row = self._repo.create(
            user_id=user_id,
            title=resolved_title[:150],
            message=message,
            type=ntype.value,
        )
        if send_email:
            self._email.send(to_user_id=user_id, subject=resolved_title, body=message)
        return row
