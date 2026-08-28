"""
FastAPI dependencies: database session, authentication, role guards and
service wiring. Routers stay thin because everything they need is assembled
here and injected.
"""
from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import NotAuthenticated, PermissionDenied
from app.core.security import decode_access_token
from app.db.session import get_db
from app.notifications.service import NotificationService
from app.repositories.repositories import (
    AcademicRepository, BusyRepository, FacultyRepository,
    NotificationRepository, QueueRepository, RequestRepository,
    SettingsRepository, SlotRepository, StudentRepository, TimetableRepository,
    TokenRepository, UserRepository,
)
from app.services.admin_user_service import AdminAccountService
from app.services.appointment_service import AppointmentService
from app.services.free_slot_service import FreeSlotService
from app.services.queue_service import QueueService
from app.services.token_service import TokenService


class AuthContext:
    """The authenticated caller."""

    def __init__(self, user_id: int, roles: list[str]) -> None:
        self.user_id = user_id
        self.roles = roles

    def has(self, *roles: Role) -> bool:
        wanted = {r.value for r in roles}
        return bool(wanted & set(self.roles))

    def require(self, *roles: Role) -> None:
        if not self.has(*roles):
            raise PermissionDenied(
                "requires role: " + " or ".join(r.value for r in roles))


def get_current_user(authorization: str | None = Header(default=None)) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise NotAuthenticated("missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except Exception:
        raise NotAuthenticated("invalid or expired token")
    sub = payload.get("sub")
    if sub is None:
        raise NotAuthenticated("token has no subject")
    return AuthContext(int(sub), list(payload.get("roles", [])))


# --- role guards ------------------------------------------------------------
def require_faculty(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
    auth.require(Role.FACULTY)
    return auth


def require_student(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
    auth.require(Role.STUDENT)
    return auth


def require_admin(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
    auth.require(Role.SUPER_ADMIN, Role.DEPARTMENT_ADMIN)
    return auth


# --- service factories ------------------------------------------------------
def get_free_slot_service(db: Session = Depends(get_db)) -> FreeSlotService:
    return FreeSlotService(
        slots=SlotRepository(db),
        timetable=TimetableRepository(db),
        requests=RequestRepository(db),
        busy=BusyRepository(db),
        settings_repo=SettingsRepository(db),
    )


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(NotificationRepository(db))


def get_appointment_service(
    db: Session = Depends(get_db),
    free_slots: FreeSlotService = Depends(get_free_slot_service),
    notifications: NotificationService = Depends(get_notification_service),
) -> AppointmentService:
    return AppointmentService(
        requests=RequestRepository(db),
        queue=QueueRepository(db),
        faculty=FacultyRepository(db),
        students=StudentRepository(db),
        slots=SlotRepository(db),
        busy=BusyRepository(db),
        free_slots=free_slots,
        tokens=TokenService(TokenRepository(db)),
        notifications=notifications,
    )


def get_queue_service(
    db: Session = Depends(get_db),
    notifications: NotificationService = Depends(get_notification_service),
) -> QueueService:
    return QueueService(
        queue=QueueRepository(db),
        requests=RequestRepository(db),
        slots=SlotRepository(db),
        settings_repo=SettingsRepository(db),
        notifications=notifications,
    )


def get_user_repo(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_admin_account_service(db: Session = Depends(get_db)) -> AdminAccountService:
    return AdminAccountService(
        users=UserRepository(db),
        students=StudentRepository(db),
        faculty=FacultyRepository(db),
        academic=AcademicRepository(db),
    )
