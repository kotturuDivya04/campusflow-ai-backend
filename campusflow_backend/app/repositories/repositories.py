"""
Repository layer. ALL database queries live here (brief: "database queries
belong in repositories"). Services depend on repositories, never on the ORM
session directly for query construction. Each repository takes a Session.

Repositories also project ORM rows into the pure-logic dataclasses
(app.services.domain) that the Free Slot Engine / priority / ETA consume, which
is what keeps the decision core ORM-free and unit-testable.
"""
from __future__ import annotations

import datetime as _dt

from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.orm import Session, aliased

from app.core.enums import DAYS_OF_WEEK, QueueState, RequestStatus
from app.models import (
    AcademicSlot, Department, Faculty, FacultyBusyBlock, Notification,
    QueueEntry, Request, Role, Section, Student, SystemSetting, Timetable,
    Token, User, UserRole,
)
from app.services.domain import QueueEntryView, SlotView


# --------------------------------------------------------------------------
class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def roles_for(self, user_id: int) -> list[str]:
        rows = self.db.execute(
            select(Role.name).join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        ).all()
        return [r[0] for r in rows]

    def list_users(self, limit: int = 100) -> list[User]:
        return list(self.db.scalars(select(User).limit(limit)))

    def by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def role_by_name(self, name: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.name == name))

    def create(self, **kwargs) -> User:
        """Insert a users row. Flush only — the route owns the commit."""
        u = User(**kwargs)
        self.db.add(u)
        self.db.flush()
        return u

    def assign_role(self, user_id: int, role_id: int) -> UserRole:
        link = UserRole(user_id=user_id, role_id=role_id)
        self.db.add(link)
        self.db.flush()
        return link


# --------------------------------------------------------------------------
class FacultyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, faculty_id: int) -> Faculty | None:
        return self.db.get(Faculty, faculty_id)

    def search(self, q: str | None = None, limit: int = 50) -> list[Faculty]:
        stmt = select(Faculty).join(User, User.id == Faculty.id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                (User.first_name.ilike(like)) | (User.last_name.ilike(like))
                | (Faculty.faculty_code.ilike(like))
            )
        return list(self.db.scalars(stmt.limit(limit)))

    def by_code(self, faculty_code: str) -> Faculty | None:
        return self.db.scalar(select(Faculty).where(Faculty.faculty_code == faculty_code))

    def create(self, **kwargs) -> Faculty:
        """Insert a faculty row (id == users.id). Flush only."""
        f = Faculty(**kwargs)
        self.db.add(f)
        self.db.flush()
        return f


class StudentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, student_id: int) -> Student | None:
        return self.db.get(Student, student_id)

    def by_roll_number(self, roll_number: str) -> Student | None:
        return self.db.scalar(select(Student).where(Student.roll_number == roll_number))

    def create(self, **kwargs) -> Student:
        """Insert a students row (id == users.id). Flush only."""
        s = Student(**kwargs)
        self.db.add(s)
        self.db.flush()
        return s


class AcademicRepository:
    """Read-only lookups for the academic reference tables (departments,
    sections). Used to validate FK targets before an insert so a bad id becomes
    a 422/404 instead of an IntegrityError."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def department_exists(self, department_id: int) -> bool:
        return self.db.get(Department, department_id) is not None

    def section_exists(self, section_id: int) -> bool:
        return self.db.get(Section, section_id) is not None


# --------------------------------------------------------------------------
class SlotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def all_slots(self) -> list[AcademicSlot]:
        return list(self.db.scalars(select(AcademicSlot).order_by(AcademicSlot.start_time)))

    def by_id(self, slot_id: int) -> AcademicSlot | None:
        return self.db.get(AcademicSlot, slot_id)

    def as_views(self) -> list[SlotView]:
        return [
            SlotView(s.id, s.slot_name, s.start_time, s.end_time)
            for s in self.all_slots()
        ]

    def create(self, slot_name: str, start_time: _dt.time, end_time: _dt.time) -> AcademicSlot:
        s = AcademicSlot(slot_name=slot_name, start_time=start_time, end_time=end_time)
        self.db.add(s)
        self.db.flush()
        return s


class TimetableRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def teaching_slot_ids(self, faculty_id: int, day_of_week: str,
                          academic_year: int, semester: str) -> set[int]:
        rows = self.db.execute(
            select(Timetable.academic_slot_id).where(and_(
                Timetable.faculty_id == faculty_id,
                Timetable.day_of_week == day_of_week,
                Timetable.academic_year == academic_year,
                Timetable.semester == semester,
            ))
        ).all()
        return {r[0] for r in rows}

    def for_faculty(self, faculty_id: int) -> list[Timetable]:
        return list(self.db.scalars(
            select(Timetable).where(Timetable.faculty_id == faculty_id)))

    def exists(self, *, section_id: int, faculty_id: int, classroom_id: int,
               academic_slot_id: int, day_of_week: str, academic_year: int,
               semester: str) -> bool:
        stmt = select(Timetable.id).where(and_(
            Timetable.faculty_id == faculty_id,
            Timetable.day_of_week == day_of_week,
            Timetable.academic_slot_id == academic_slot_id,
            Timetable.academic_year == academic_year,
            Timetable.semester == semester,
        ))
        return self.db.scalar(stmt) is not None

    def add(self, **kwargs) -> Timetable:
        row = Timetable(**kwargs)
        self.db.add(row)
        self.db.flush()
        return row


# --------------------------------------------------------------------------
class RequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, request_id: int) -> Request | None:
        return self.db.get(Request, request_id)

    def create(self, **kwargs) -> Request:
        r = Request(**kwargs)
        self.db.add(r)
        self.db.flush()
        return r

    def for_student(self, student_id: int) -> list[Request]:
        return list(self.db.scalars(
            select(Request).where(Request.student_id == student_id)
            .order_by(Request.created_at.desc())))

    def pending_for_faculty(self, faculty_id: int) -> list[Request]:
        return list(self.db.scalars(
            select(Request).where(and_(
                Request.faculty_id == faculty_id,
                Request.status == RequestStatus.PENDING.value,
            )).order_by(Request.created_at)))

    def open_for_student_faculty(self, student_id: int, faculty_id: int) -> list[Request]:
        """Non-terminal (Pending/Approved/Rescheduled) requests for a pair."""
        return list(self.db.scalars(
            select(Request).where(and_(
                Request.student_id == student_id,
                Request.faculty_id == faculty_id,
                Request.status.in_([
                    RequestStatus.PENDING.value,
                    RequestStatus.APPROVED.value,
                    RequestStatus.RESCHEDULED.value,
                ]),
            ))))

    def update_status(self, request: Request, status: str,
                      scheduled_time: _dt.datetime | None = "keep") -> Request:
        request.status = status
        if scheduled_time != "keep":
            request.scheduled_time = scheduled_time
        self.db.flush()
        return request

    def approved_slot_ids_on_date(self, faculty_id: int, date: _dt.date) -> set[int]:
        """
        Slot ids occupied by an APPROVED appointment for this faculty on this
        date. Derived from queue_entries (which carry the dated slot). Pending
        requests are intentionally excluded (documented capacity behaviour).
        """
        rows = self.db.execute(
            select(QueueEntry.academic_slot_id).where(and_(
                QueueEntry.faculty_id == faculty_id,
                QueueEntry.meeting_date == date,
                QueueEntry.state.in_([s.value for s in (
                    QueueState.WAITING, QueueState.CHECKED_IN,
                    QueueState.READY, QueueState.IN_PROGRESS, QueueState.COMPLETED)]),
            ))
        ).all()
        return {r[0] for r in rows}

    def list_for_admin(
        self, *, status: str | None = None, faculty_id: int | None = None,
        student_id: int | None = None, date_from: _dt.date | None = None,
        date_to: _dt.date | None = None, limit: int = 100, offset: int = 0,
    ):
        """
        READ-ONLY cross-cutting listing of existing `requests` rows for the
        Admin view. Everything is fetched in ONE joined statement (students +
        their users row, faculty + their users row, and the optional
        queue_entries/academic_slots pair) so rendering N appointments costs one
        query rather than N.

        The effective meeting date is COALESCE(queue_entries.meeting_date,
        requests.scheduled_time::date): once approved the authoritative dated
        slot lives on the queue entry, before that only the encoded
        scheduled_time exists. Rows with neither are unreachable by the date
        filters — documented, not worked around with a schema change.
        """
        su = aliased(User)   # the student's users row
        fu = aliased(User)   # the faculty's users row

        effective_date = func.coalesce(
            QueueEntry.meeting_date, cast(Request.scheduled_time, Date))

        stmt = (
            select(
                Request.id.label("id"),
                Request.student_id.label("student_id"),
                Request.faculty_id.label("faculty_id"),
                Request.request_type.label("request_type"),
                Request.title.label("title"),
                Request.description.label("description"),
                Request.status.label("status"),
                Request.scheduled_time.label("scheduled_time"),
                Request.created_at.label("created_at"),
                su.first_name.label("student_first_name"),
                su.last_name.label("student_last_name"),
                su.email.label("student_email"),
                Student.roll_number.label("student_roll_number"),
                fu.first_name.label("faculty_first_name"),
                fu.last_name.label("faculty_last_name"),
                fu.email.label("faculty_email"),
                Faculty.faculty_code.label("faculty_code"),
                QueueEntry.meeting_date.label("meeting_date"),
                QueueEntry.academic_slot_id.label("academic_slot_id"),
                QueueEntry.token_number.label("token_number"),
                QueueEntry.state.label("queue_state"),
                AcademicSlot.slot_name.label("slot_name"),
                AcademicSlot.start_time.label("slot_start_time"),
                AcademicSlot.end_time.label("slot_end_time"),
            )
            .join(Student, Student.id == Request.student_id)
            .join(su, su.id == Student.id)
            .join(Faculty, Faculty.id == Request.faculty_id)
            .join(fu, fu.id == Faculty.id)
            .outerjoin(QueueEntry, QueueEntry.request_id == Request.id)
            .outerjoin(AcademicSlot, AcademicSlot.id == QueueEntry.academic_slot_id)
        )

        if status is not None:
            stmt = stmt.where(Request.status == status)
        if faculty_id is not None:
            stmt = stmt.where(Request.faculty_id == faculty_id)
        if student_id is not None:
            stmt = stmt.where(Request.student_id == student_id)
        if date_from is not None:
            stmt = stmt.where(effective_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(effective_date <= date_to)

        stmt = stmt.order_by(Request.created_at.desc(), Request.id.desc())
        return list(self.db.execute(stmt.limit(limit).offset(offset)).all())

    def duplicate_exists(self, *, student_id: int, faculty_id: int,
                         date: _dt.date, slot_id: int) -> bool:
        """A non-terminal request from the same student for the same dated slot."""
        rows = self.db.execute(
            select(QueueEntry.id).where(and_(
                QueueEntry.student_id == student_id,
                QueueEntry.faculty_id == faculty_id,
                QueueEntry.meeting_date == date,
                QueueEntry.academic_slot_id == slot_id,
                QueueEntry.state.in_([QueueState.WAITING.value, QueueState.CHECKED_IN.value,
                                      QueueState.READY.value, QueueState.IN_PROGRESS.value]),
            ))
        ).all()
        return bool(rows)


class BusyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def busy_slot_ids(self, faculty_id: int, date: _dt.date) -> set[int]:
        rows = self.db.execute(
            select(FacultyBusyBlock.academic_slot_id).where(and_(
                FacultyBusyBlock.faculty_id == faculty_id,
                FacultyBusyBlock.block_date == date,
            ))
        ).all()
        return {r[0] for r in rows}

    def get(self, faculty_id: int, date: _dt.date, slot_id: int) -> FacultyBusyBlock | None:
        return self.db.scalar(select(FacultyBusyBlock).where(and_(
            FacultyBusyBlock.faculty_id == faculty_id,
            FacultyBusyBlock.block_date == date,
            FacultyBusyBlock.academic_slot_id == slot_id,
        )))

    def get_or_create(self, *, faculty_id: int, block_date: _dt.date,
                      academic_slot_id: int, reason: str | None = None,
                      created_by: int | None = None) -> tuple[FacultyBusyBlock, bool]:
        """Idempotent: returns (block, created). A repeat Mark Busy on the same
        (faculty, date, slot) reuses the existing block instead of violating
        uq_faculty_busy."""
        existing = self.get(faculty_id, block_date, academic_slot_id)
        if existing is not None:
            return existing, False
        b = FacultyBusyBlock(faculty_id=faculty_id, block_date=block_date,
                             academic_slot_id=academic_slot_id, reason=reason,
                             created_by=created_by)
        self.db.add(b)
        self.db.flush()
        return b, True

    def add(self, **kwargs) -> FacultyBusyBlock:
        b = FacultyBusyBlock(**kwargs)
        self.db.add(b)
        self.db.flush()
        return b


# --------------------------------------------------------------------------
class QueueRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, qid: int) -> QueueEntry | None:
        return self.db.get(QueueEntry, qid)

    def by_request(self, request_id: int) -> QueueEntry | None:
        return self.db.scalar(select(QueueEntry).where(QueueEntry.request_id == request_id))

    def create(self, **kwargs) -> QueueEntry:
        q = QueueEntry(**kwargs)
        self.db.add(q)
        self.db.flush()
        return q

    def revive(self, entry: QueueEntry, *, meeting_date: _dt.date,
               academic_slot_id: int, token_number: int,
               access_token_id: int | None, priority_class: str,
               priority_score: int) -> QueueEntry:
        """Reset a WITHDRAWN/NO_SHOW entry back to WAITING on a new dated slot.
        Used when a rescheduled request is re-approved; respects the one-entry-
        per-request UNIQUE(request_id) constraint."""
        entry.meeting_date = meeting_date
        entry.academic_slot_id = academic_slot_id
        entry.token_number = token_number
        entry.access_token_id = access_token_id
        entry.priority_class = priority_class
        entry.priority_score = priority_score
        entry.state = QueueState.WAITING.value
        entry.checked_in_at = None
        entry.started_at = None
        entry.completed_at = None
        entry.delay_minutes = 0
        entry.exchanged_with_id = None
        self.db.flush()
        return entry

    def flush(self) -> None:
        self.db.flush()

    def next_token_number(self, faculty_id: int, date: _dt.date, slot_id: int) -> int:
        rows = self.db.execute(
            select(QueueEntry.token_number).where(and_(
                QueueEntry.faculty_id == faculty_id,
                QueueEntry.meeting_date == date,
                QueueEntry.academic_slot_id == slot_id,
            ))
        ).all()
        return (max((r[0] for r in rows), default=0)) + 1

    def session_entries(self, faculty_id: int, date: _dt.date,
                        slot_id: int | None = None) -> list[QueueEntry]:
        conds = [QueueEntry.faculty_id == faculty_id, QueueEntry.meeting_date == date]
        if slot_id is not None:
            conds.append(QueueEntry.academic_slot_id == slot_id)
        return list(self.db.scalars(
            select(QueueEntry).where(and_(*conds)).order_by(QueueEntry.token_number)))

    def for_student(self, student_id: int) -> list[QueueEntry]:
        return list(self.db.scalars(
            select(QueueEntry).where(QueueEntry.student_id == student_id)
            .order_by(QueueEntry.created_at.desc())))

    def active_on_slot(self, faculty_id: int, date: _dt.date, slot_id: int) -> list[QueueEntry]:
        """Non-terminal queue entries on a dated slot (for Busy handling)."""
        return list(self.db.scalars(
            select(QueueEntry).where(and_(
                QueueEntry.faculty_id == faculty_id,
                QueueEntry.meeting_date == date,
                QueueEntry.academic_slot_id == slot_id,
                QueueEntry.state.in_([s.value for s in (
                    QueueState.WAITING, QueueState.CHECKED_IN,
                    QueueState.READY, QueueState.IN_PROGRESS)]),
            ))))

    @staticmethod
    def to_view(q: QueueEntry) -> QueueEntryView:
        return QueueEntryView(
            id=q.id, student_id=q.student_id, token_number=q.token_number,
            priority_class=q.priority_class, state=q.state,
            booking_ts=q.created_at, entered_at=q.created_at,
            effective_minutes=0, checked_in_at=q.checked_in_at,
            started_at=q.started_at, completed_at=q.completed_at,
            delay_minutes=q.delay_minutes,
        )


class TokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> Token:
        t = Token(**kwargs)
        self.db.add(t)
        self.db.flush()
        return t


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> Notification:
        n = Notification(**kwargs)
        self.db.add(n)
        self.db.flush()
        return n

    def for_user(self, user_id: int, limit: int = 50) -> list[Notification]:
        return list(self.db.scalars(
            select(Notification).where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc()).limit(limit)))

    def by_id(self, notification_id: int) -> Notification | None:
        return self.db.get(Notification, notification_id)

    def list_all(self, *, user_id: int | None = None, type: str | None = None,
                 is_read: bool | None = None, limit: int = 100,
                 offset: int = 0) -> list[Notification]:
        """READ-ONLY system-wide listing of the existing notifications table for
        the Admin view. Same model, same table, same rows the per-user
        `for_user` read returns — only the scope differs."""
        stmt = select(Notification)
        if user_id is not None:
            stmt = stmt.where(Notification.user_id == user_id)
        if type is not None:
            stmt = stmt.where(Notification.type == type)
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)
        stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        return list(self.db.scalars(stmt.limit(limit).offset(offset)))

    def mark_read(self, notification: Notification) -> Notification:
        notification.is_read = True
        self.db.flush()
        return notification

    def mark_all_read(self, user_id: int) -> int:
        rows = self.db.scalars(
            select(Notification).where(and_(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            ))).all()
        for r in rows:
            r.is_read = True
        self.db.flush()
        return len(rows)


class SettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, key: str) -> str | None:
        row = self.db.scalar(select(SystemSetting).where(SystemSetting.setting_key == key))
        return row.setting_value if row else None

    def get_int(self, key: str, default: int) -> int:
        v = self.get(key)
        try:
            return int(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def all(self) -> list[SystemSetting]:
        return list(self.db.scalars(select(SystemSetting)))

    def set(self, key: str, value: str) -> SystemSetting:
        row = self.db.scalar(select(SystemSetting).where(SystemSetting.setting_key == key))
        if row is None:
            row = SystemSetting(setting_key=key, setting_value=value)
            self.db.add(row)
        else:
            row.setting_value = value
        self.db.flush()
        return row
