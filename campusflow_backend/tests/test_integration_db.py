"""
Real-database integration tests (SQLite).

Unlike tests/test_api.py (which drives the FastAPI HTTP layer and needs the full
web stack), this module exercises the ORM, repositories and services directly
against a REAL SQLAlchemy engine with foreign keys enforced. It needs only
SQLAlchemy — no FastAPI, no pydantic, no PostgreSQL — so it runs as soon as
`pip install -r requirements.txt` is done, and auto-skips if SQLAlchemy is
absent.

It builds its own SQLite engine from the ORM metadata and never imports
app.db.session, so it is independent of CAMPUSFLOW_DATABASE_URL. A SQLite-only
shim renders BigInteger primary keys as INTEGER so SQLite autoincrements them;
production creates the tables from the canonical `GENERATED AS IDENTITY` SQL.

These are the same checks used to harden the backend during verification
(see VERIFICATION_REPORT.md): 34 assertions across the appointment, queue,
notification and access-token flows.
"""
from __future__ import annotations

import datetime as _dt
import unittest

try:
    from sqlalchemy import BigInteger, create_engine, event, select
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.orm import sessionmaker
    _HAVE_SA = True
except Exception:  # pragma: no cover
    _HAVE_SA = False

pytestmark = []

if _HAVE_SA:
    @compiles(BigInteger, "sqlite")
    def _bigint_as_integer_on_sqlite(type_, compiler, **kw):  # noqa: ANN001
        # SQLite autoincrements INTEGER PRIMARY KEY, not BIGINT. Production uses
        # 001_core_schema.sql (GENERATED AS IDENTITY); this affects SQLite only.
        return "INTEGER"

    @event.listens_for(Engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


UTC = _dt.timezone.utc


def _next_monday() -> _dt.date:
    d = _dt.date.today()
    while d.weekday() != 0 or d <= _dt.date.today():
        d += _dt.timedelta(days=1)
    return d


@unittest.skipUnless(_HAVE_SA, "SQLAlchemy not installed")
class DatabaseIntegrationTests(unittest.TestCase):
    Session = None

    @classmethod
    def setUpClass(cls):
        from app.db.base import Base
        cls.Base = Base
        cls.engine = create_engine("sqlite://")  # shared in-memory for this run
        # keep a single connection so the in-memory DB persists across sessions
        cls._conn = cls.engine.connect()
        cls.Session = sessionmaker(bind=cls.engine, expire_on_commit=False, future=True)

    def _fresh_schema(self):
        self.Base.metadata.drop_all(self.engine)
        self.Base.metadata.create_all(self.engine)

    # -- fixture -----------------------------------------------------------
    def _seed(self):
        from app.models import (
            AcademicSlot, Classroom, Department, Faculty, Role, Section,
            Student, Subject, SystemSetting, Timetable, User, UserRole,
        )
        self._fresh_schema()
        db = self.Session()
        roles = {n: Role(name=n) for n in ("Faculty", "Student", "DepartmentAdmin")}
        db.add_all(roles.values()); db.flush()
        dept = Department(code="CSE", name="CS"); db.add(dept); db.flush()
        sec = Section(name="CSE-3A", department_id=dept.id, academic_year=2026, semester="Fall")
        db.add(sec); db.flush()
        subj = Subject(code="CS301", name="Algo", credits=4, department_id=dept.id)
        room = Classroom(room_number="A-101", building="Main", capacity=60, type="Lecture")
        db.add_all([subj, room]); db.flush()
        fu = User(username="f1", email="f1@x", password_hash="x", first_name="F", last_name="A", status="Active")
        su = User(username="s1", email="s1@x", password_hash="x", first_name="S", last_name="B", status="Active")
        su2 = User(username="s2", email="s2@x", password_hash="x", first_name="T", last_name="C", status="Active")
        db.add_all([fu, su, su2]); db.flush()
        db.add_all([UserRole(user_id=fu.id, role_id=roles["Faculty"].id),
                    UserRole(user_id=su.id, role_id=roles["Student"].id),
                    UserRole(user_id=su2.id, role_id=roles["Student"].id)])
        db.add_all([
            Faculty(id=fu.id, faculty_code="FAC001", department_id=dept.id, designation="Prof"),
            Student(id=su.id, roll_number="R1", department_id=dept.id, section_id=sec.id, admission_year=2024, current_semester=5),
            Student(id=su2.id, roll_number="R2", department_id=dept.id, section_id=sec.id, admission_year=2024, current_semester=5),
        ]); db.flush()
        slots = [
            AcademicSlot(slot_name="Period 1", start_time=_dt.time(9, 0), end_time=_dt.time(9, 50)),
            AcademicSlot(slot_name="Period 2", start_time=_dt.time(10, 0), end_time=_dt.time(10, 50)),
            AcademicSlot(slot_name="Period 3", start_time=_dt.time(11, 0), end_time=_dt.time(11, 50)),
            AcademicSlot(slot_name="Lunch", start_time=_dt.time(12, 20), end_time=_dt.time(13, 30)),
        ]
        db.add_all(slots); db.flush()
        db.add(Timetable(section_id=sec.id, subject_id=subj.id, faculty_id=fu.id,
                         classroom_id=room.id, academic_slot_id=slots[0].id,
                         day_of_week="Monday", academic_year=2026, semester="Fall"))
        db.add_all([
            SystemSetting(setting_key="CURRENT_ACADEMIC_YEAR", setting_value="2026"),
            SystemSetting(setting_key="CURRENT_SEMESTER", setting_value="Fall"),
            SystemSetting(setting_key="APPOINTMENT_BUFFER_MINUTES", setting_value="5"),
            SystemSetting(setting_key="DEFAULT_MEETING_MINUTES", setting_value="15"),
        ])
        db.commit()
        ids = dict(fac=fu.id, st=su.id, st2=su2.id, p1=slots[0].id,
                   p2=slots[1].id, p3=slots[2].id, lunch=slots[3].id)
        db.close()
        return ids

    def _services(self, db):
        from app.repositories.repositories import (
            BusyRepository, FacultyRepository, NotificationRepository, QueueRepository,
            RequestRepository, SettingsRepository, SlotRepository, StudentRepository,
            TimetableRepository, TokenRepository,
        )
        from app.notifications.service import NotificationService
        from app.services.appointment_service import AppointmentService
        from app.services.free_slot_service import FreeSlotService
        from app.services.queue_service import QueueService
        from app.services.token_service import TokenService
        free = FreeSlotService(slots=SlotRepository(db), timetable=TimetableRepository(db),
                               requests=RequestRepository(db), busy=BusyRepository(db),
                               settings_repo=SettingsRepository(db))
        notif = NotificationService(NotificationRepository(db))
        appt = AppointmentService(requests=RequestRepository(db), queue=QueueRepository(db),
                                  faculty=FacultyRepository(db), students=StudentRepository(db),
                                  slots=SlotRepository(db), busy=BusyRepository(db), free_slots=free,
                                  tokens=TokenService(TokenRepository(db)), notifications=notif)
        queue = QueueService(queue=QueueRepository(db), requests=RequestRepository(db),
                             slots=SlotRepository(db), settings_repo=SettingsRepository(db),
                             notifications=notif)
        return free, appt, queue

    # -- tests -------------------------------------------------------------
    def test_free_slots_exclude_teaching_and_break_in_order(self):
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, _, _ = self._services(db)
        names = [s.slot_name for s in free.compute(faculty_id=ids["fac"], date=MON)]
        self.assertNotIn("Period 1", names)      # taught
        self.assertNotIn("Lunch", names)         # break by name
        starts = [s.start_time for s in free.compute(faculty_id=ids["fac"], date=MON)]
        self.assertEqual(starts, sorted(starts))
        db.close()

    def test_submit_pending_and_notify_and_duplicate_rejected(self):
        from app.core.errors import DuplicateRequest
        from app.models import Notification
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, _ = self._services(db)
        req = appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                          slot_id=ids["p2"], title="D", description="x"); db.commit()
        self.assertEqual(req.status, "Pending")
        self.assertTrue(db.scalars(select(Notification).where(Notification.user_id == ids["fac"])).all())
        with self.assertRaises(DuplicateRequest):
            appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                        slot_id=ids["p2"], title="D2", description="x")
        db.rollback(); db.close()

    def test_approve_creates_token_and_queue_and_blocks_double_approve(self):
        from app.core.errors import Conflict, IllegalTransition
        from app.models import QueueEntry, Token
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, _ = self._services(db)
        req = appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                          slot_id=ids["p2"], title="D", description="x"); db.commit()
        r, entry = appt.approve(request_id=req.id, acting_faculty_id=ids["fac"]); db.commit()
        self.assertEqual(r.status, "Approved")
        self.assertEqual(entry.token_number, 1)
        self.assertIsNotNone(entry.access_token_id)
        self.assertEqual(db.get(Token, entry.access_token_id).token_type, "REQUEST_ACCESS")
        with self.assertRaises((IllegalTransition, Conflict)):
            appt.approve(request_id=req.id, acting_faculty_id=ids["fac"]); db.commit()
        db.rollback()
        cnt = len(db.scalars(select(QueueEntry).where(QueueEntry.request_id == req.id)).all())
        self.assertEqual(cnt, 1)
        db.close()

    def test_shared_primary_key_correspondence(self):
        from app.models import Faculty, Student, User
        ids = self._seed()
        db = self.Session()
        self.assertEqual(db.get(Faculty, ids["fac"]).id, db.get(User, ids["fac"]).id)
        self.assertEqual(db.get(Student, ids["st"]).id, ids["st"])
        db.close()

    def test_db_rejects_duplicate_token_number(self):
        from app.models import QueueEntry, Request
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, _ = self._services(db)
        req = appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                          slot_id=ids["p2"], title="D", description="x"); db.commit()
        _, entry = appt.approve(request_id=req.id, acting_faculty_id=ids["fac"]); db.commit()
        throwaway = Request(student_id=ids["st2"], faculty_id=ids["fac"], request_type="Appointment",
                            title="p", description="x", status="Approved")
        db.add(throwaway); db.flush()
        db.add(QueueEntry(request_id=throwaway.id, faculty_id=ids["fac"], student_id=ids["st2"],
                          meeting_date=entry.meeting_date, academic_slot_id=entry.academic_slot_id,
                          token_number=entry.token_number, priority_class="CONFIRMED",
                          priority_score=0, state="WAITING"))
        with self.assertRaises(IntegrityError):
            db.commit()
        db.rollback(); db.close()

    def test_meeting_lifecycle_timestamps_and_illegal_transition(self):
        from app.core.errors import IllegalTransition
        from app.models import QueueEntry
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, queue = self._services(db)
        req = appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                          slot_id=ids["p2"], title="D", description="x"); db.commit()
        _, entry = appt.approve(request_id=req.id, acting_faculty_id=ids["fac"]); db.commit()
        eid = entry.id
        # cannot complete before begin
        with self.assertRaises(IllegalTransition):
            queue.complete_meeting(entry_id=eid, acting_faculty_id=ids["fac"]); db.commit()
        db.rollback()
        queue.check_in(entry_id=eid, acting_student_id=ids["st"]); db.commit()
        self.assertIsNotNone(db.get(QueueEntry, eid).checked_in_at)
        queue.begin_meeting(entry_id=eid, acting_faculty_id=ids["fac"]); db.commit()
        self.assertIsNotNone(db.get(QueueEntry, eid).started_at)
        queue.complete_meeting(entry_id=eid, acting_faculty_id=ids["fac"]); db.commit()
        e = db.get(QueueEntry, eid)
        self.assertEqual(e.state, "COMPLETED")
        self.assertIsNotNone(e.completed_at)
        db.close()

    def test_eta_available_and_non_negative(self):
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, queue = self._services(db)
        req = appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                          slot_id=ids["p2"], title="D", description="x"); db.commit()
        _, entry = appt.approve(request_id=req.id, acting_faculty_id=ids["fac"]); db.commit()
        eta = queue.eta_for(entry_id=entry.id)
        self.assertFalse(eta.unavailable)
        self.assertGreaterEqual(eta.estimated_minutes, 0)
        db.close()

    def test_mark_busy_reconciles_and_is_idempotent(self):
        from app.models import FacultyBusyBlock, QueueEntry, Request
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, _ = self._services(db)
        req = appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                          slot_id=ids["p3"], title="D", description="x"); db.commit()
        _, entry = appt.approve(request_id=req.id, acting_faculty_id=ids["fac"]); db.commit()
        appt.mark_busy(faculty_id=ids["fac"], acting_faculty_id=ids["fac"], date=MON,
                       slot_id=ids["p3"], reason="m"); db.commit()
        self.assertEqual(db.get(QueueEntry, entry.id).state, "WITHDRAWN")
        self.assertEqual(db.get(Request, req.id).status, "Rescheduled")
        # idempotent second call
        appt.mark_busy(faculty_id=ids["fac"], acting_faculty_id=ids["fac"], date=MON,
                       slot_id=ids["p3"], reason="again"); db.commit()
        blocks = db.scalars(select(FacultyBusyBlock).where(
            FacultyBusyBlock.faculty_id == ids["fac"],
            FacultyBusyBlock.block_date == MON,
            FacultyBusyBlock.academic_slot_id == ids["p3"])).all()
        self.assertEqual(len(blocks), 1)
        db.close()

    def test_reschedule_then_reapproval_yields_waiting_entry_on_new_slot(self):
        from app.models import QueueEntry, Request
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, _ = self._services(db)
        req = appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                          slot_id=ids["p2"], title="D", description="x"); db.commit()
        _, entry = appt.approve(request_id=req.id, acting_faculty_id=ids["fac"]); db.commit()
        appt.reschedule(request_id=req.id, acting_faculty_id=ids["fac"], date=MON,
                        slot_id=ids["p3"], note="moved"); db.commit()
        self.assertEqual(db.get(Request, req.id).status, "Rescheduled")
        self.assertEqual(db.get(QueueEntry, entry.id).state, "WITHDRAWN")
        _, e2 = appt.approve(request_id=req.id, acting_faculty_id=ids["fac"]); db.commit()
        self.assertEqual(e2.state, "WAITING")
        self.assertEqual(e2.academic_slot_id, ids["p3"])
        self.assertIsNone(e2.checked_in_at)
        db.close()

    def test_token_exchange_authorization_swap_and_in_progress_guard(self):
        from app.core.errors import Conflict, PermissionDenied
        from app.models import QueueEntry, Request
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, queue = self._services(db)
        ra = appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                         slot_id=ids["p2"], title="a", description="x"); db.commit()
        _, ea = appt.approve(request_id=ra.id, acting_faculty_id=ids["fac"]); db.commit()
        rextra = Request(student_id=ids["st2"], faculty_id=ids["fac"], request_type="Appointment",
                         title="b", description="x", status="Approved"); db.add(rextra); db.flush()
        eb = QueueEntry(request_id=rextra.id, faculty_id=ids["fac"], student_id=ids["st2"],
                        meeting_date=ea.meeting_date, academic_slot_id=ea.academic_slot_id,
                        token_number=2, priority_class="CONFIRMED", priority_score=0, state="WAITING")
        db.add(eb); db.commit()
        ea_id, eb_id = ea.id, eb.id
        a_num, b_num = ea.token_number, eb.token_number
        # non-owner blocked
        with self.assertRaises(PermissionDenied):
            queue.exchange(entry_id=ea_id, other_entry_id=eb_id, acting_student_id=ids["st2"])
        db.rollback()
        # owner swaps
        queue.exchange(entry_id=ea_id, other_entry_id=eb_id, acting_student_id=ids["st"]); db.commit()
        self.assertEqual(db.get(QueueEntry, ea_id).token_number, b_num)
        self.assertEqual(db.get(QueueEntry, eb_id).token_number, a_num)
        self.assertEqual(db.get(QueueEntry, ea_id).exchanged_with_id, eb_id)
        # blocked once in progress
        queue.check_in(entry_id=ea_id, acting_student_id=ids["st"]); db.commit()
        queue.begin_meeting(entry_id=ea_id, acting_faculty_id=ids["fac"]); db.commit()
        with self.assertRaises(Conflict):
            queue.exchange(entry_id=ea_id, other_entry_id=eb_id, acting_student_id=ids["st"])
        db.rollback(); db.close()

    def test_notifications_mark_read_and_mark_all_read(self):
        from app.models import Notification
        from app.repositories.repositories import NotificationRepository
        ids = self._seed(); MON = _next_monday()
        db = self.Session(); free, appt, _ = self._services(db)
        appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                    slot_id=ids["p2"], title="D", description="x"); db.commit()
        repo = NotificationRepository(db)
        n = repo.for_user(ids["fac"])[0]
        self.assertFalse(n.is_read)
        repo.mark_read(n); db.commit()
        self.assertTrue(db.get(Notification, n.id).is_read)
        appt.submit(student_id=ids["st"], faculty_id=ids["fac"], date=MON,
                    slot_id=ids["p3"], title="D2", description="x"); db.commit()
        repo.mark_all_read(ids["fac"]); db.commit()
        remaining = db.scalars(select(Notification).where(
            Notification.user_id == ids["fac"], Notification.is_read == False)).all()  # noqa: E712
        self.assertEqual(len(remaining), 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
