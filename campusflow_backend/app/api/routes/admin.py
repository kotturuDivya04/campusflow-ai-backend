"""
Admin routes: academic slots, timetable records, timetable upload, user/role
listing and system settings.
"""
from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthContext, get_admin_account_service, require_admin,
)
from app.core.enums import NotificationType, RequestStatus
from app.core.errors import NotFound, ValidationFailed
from app.db.session import get_db
from app.repositories.repositories import (
    NotificationRepository, RequestRepository, SettingsRepository,
    SlotRepository, TimetableRepository, UserRepository,
)
from app.schemas import (
    AdminAppointmentOut, AdminNotificationOut, CurrentUser, FacultyCreate,
    FacultyProfile, ImportSummary, SettingOut, SettingUpdate, SlotCreate,
    SlotOut, StudentCreate, StudentProfile, TimetableRow,
)
from app.services.admin_user_service import AdminAccountService
from app.services.timetable_importer import (
    TimetableImporter, parse_csv, parse_json,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# --- academic slots ---------------------------------------------------------
@router.get("/slots", response_model=list[SlotOut])
def list_slots(auth: AuthContext = Depends(require_admin),
               db: Session = Depends(get_db)):
    return SlotRepository(db).all_slots()


@router.post("/slots", response_model=SlotOut, status_code=201)
def create_slot(payload: SlotCreate,
                auth: AuthContext = Depends(require_admin),
                db: Session = Depends(get_db)):
    if payload.end_time <= payload.start_time:
        raise ValidationFailed("end_time must be after start_time")
    slot = SlotRepository(db).create(
        slot_name=payload.slot_name, start_time=payload.start_time,
        end_time=payload.end_time)
    db.commit()
    return slot


# --- timetable --------------------------------------------------------------
@router.get("/timetable/{faculty_id}", response_model=list[TimetableRow])
def timetable_for_faculty(faculty_id: int,
                          auth: AuthContext = Depends(require_admin),
                          db: Session = Depends(get_db)):
    return TimetableRepository(db).for_faculty(faculty_id)


@router.post("/timetable/upload", response_model=ImportSummary)
async def upload_timetable(file: UploadFile = File(...),
                           auth: AuthContext = Depends(require_admin),
                           db: Session = Depends(get_db)):
    """
    Accepts a CSV or JSON timetable export. Parsing is pure (see
    services/timetable_importer.py); this route only handles transport.
    """
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    name = (file.filename or "").lower()
    parsed = parse_json(raw) if name.endswith(".json") else parse_csv(raw)
    result = TimetableImporter(db).import_rows(parsed)
    db.commit()
    return ImportSummary(**result)


# --- users ------------------------------------------------------------------
@router.get("/users", response_model=list[CurrentUser])
def list_users(auth: AuthContext = Depends(require_admin),
               db: Session = Depends(get_db)):
    repo = UserRepository(db)
    return [
        CurrentUser(
            id=u.id, username=u.username, email=u.email,
            first_name=u.first_name, last_name=u.last_name,
            roles=repo.roles_for(u.id),
        ) for u in repo.list_users()
    ]


# --- account creation -------------------------------------------------------
@router.post("/students", response_model=StudentProfile, status_code=201)
def create_student(payload: StudentCreate,
                   auth: AuthContext = Depends(require_admin),
                   db: Session = Depends(get_db),
                   service: AdminAccountService = Depends(get_admin_account_service)):
    """Create a Student account: existing `users` row + Student role + existing
    `students` row, committed as one transaction."""
    student = service.create_student(payload)
    db.commit()
    return StudentProfile(
        id=student.id, roll_number=student.roll_number,
        department_id=student.department_id, section_id=student.section_id,
        admission_year=student.admission_year,
        current_semester=student.current_semester,
        first_name=student.user.first_name, last_name=student.user.last_name,
        email=student.user.email,
    )


@router.post("/faculty", response_model=FacultyProfile, status_code=201)
def create_faculty(payload: FacultyCreate,
                   auth: AuthContext = Depends(require_admin),
                   db: Session = Depends(get_db),
                   service: AdminAccountService = Depends(get_admin_account_service)):
    """Create a Faculty account: existing `users` row + Faculty role + existing
    `faculty` row, committed as one transaction."""
    fac = service.create_faculty(payload)
    db.commit()
    return FacultyProfile(
        id=fac.id, faculty_code=fac.faculty_code,
        department_id=fac.department_id, designation=fac.designation,
        office_location=fac.office_location,
        first_name=fac.user.first_name, last_name=fac.user.last_name,
        email=fac.user.email,
    )


# --- appointments (READ-ONLY) -----------------------------------------------
@router.get("/appointments", response_model=list[AdminAppointmentOut])
def list_appointments(
    status: str | None = Query(default=None, description="Pending|Approved|Rejected|Cancelled|Rescheduled"),
    faculty_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    date_from: _dt.date | None = Query(default=None, description="YYYY-MM-DD"),
    date_to: _dt.date | None = Query(default=None, description="YYYY-MM-DD"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Read-only Admin view over the EXISTING `requests` records (CampusFlow's
    appointments), joined to student/faculty identity and, for approved
    requests, the dated slot on `queue_entries`. One query, no mutations.
    """
    if status is not None and status not in {s.value for s in RequestStatus}:
        raise ValidationFailed(
            "status must be one of: " + ", ".join(s.value for s in RequestStatus))
    if date_from is not None and date_to is not None and date_to < date_from:
        raise ValidationFailed("date_to must not be earlier than date_from")

    rows = RequestRepository(db).list_for_admin(
        status=status, faculty_id=faculty_id, student_id=student_id,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset)

    return [
        AdminAppointmentOut(
            id=r.id, student_id=r.student_id, faculty_id=r.faculty_id,
            request_type=r.request_type, title=r.title,
            description=r.description, status=r.status,
            scheduled_time=r.scheduled_time, created_at=r.created_at,
            student_name=f"{r.student_first_name} {r.student_last_name}",
            student_roll_number=r.student_roll_number,
            student_email=r.student_email,
            faculty_name=f"{r.faculty_first_name} {r.faculty_last_name}",
            faculty_code=r.faculty_code, faculty_email=r.faculty_email,
            meeting_date=r.meeting_date, academic_slot_id=r.academic_slot_id,
            slot_name=r.slot_name, slot_start_time=r.slot_start_time,
            slot_end_time=r.slot_end_time, token_number=r.token_number,
            queue_state=r.queue_state,
        ) for r in rows
    ]


# --- notifications (READ-ONLY) ----------------------------------------------
@router.get("/notifications", response_model=list[AdminNotificationOut])
def list_notifications(
    user_id: int | None = Query(default=None),
    type: str | None = Query(default=None, description="REQUEST_UPDATE|EVENT_INVITATION|ALERT|SYSTEM"),
    is_read: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Read-only system-wide view of the EXISTING `notifications` table. Same
    model, table and rows the per-user student/faculty view reads; only the
    scope differs. No delivery, no mutation.
    """
    if type is not None and type not in {t.value for t in NotificationType}:
        raise ValidationFailed(
            "type must be one of: " + ", ".join(t.value for t in NotificationType))

    return NotificationRepository(db).list_all(
        user_id=user_id, type=type, is_read=is_read, limit=limit, offset=offset)


# --- settings ---------------------------------------------------------------
@router.get("/settings", response_model=list[SettingOut])
def list_settings(auth: AuthContext = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return SettingsRepository(db).all()


@router.put("/settings/{key}", response_model=SettingOut)
def update_setting(key: str, payload: SettingUpdate,
                   auth: AuthContext = Depends(require_admin),
                   db: Session = Depends(get_db)):
    repo = SettingsRepository(db)
    if repo.get(key) is None and not key.isupper():
        raise ValidationFailed("setting keys are upper-case identifiers")
    row = repo.set(key, payload.setting_value)
    db.commit()
    return row
