from datetime import datetime, date
from typing import List, Optional
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from app.api.deps import AuthContext, get_current_user, require_faculty
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import PlacementAnnouncement

router = APIRouter(prefix="/placement", tags=["placement"])

class TargetType(str, Enum):
    ALL = "ALL"
    DEPARTMENT = "DEPARTMENT"
    SECTION = "SECTION"
    SELECTED = "SELECTED"

class AnnouncementStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

class AnnouncementCreate(BaseModel):
    title: str
    company: str
    description: str
    drive_date: Optional[date] = None
    registration_deadline: Optional[datetime] = None
    registration_link: Optional[str] = None
    min_cgpa: Optional[float] = None
    backlogs_allowed: Optional[int] = None
    target_type: TargetType = TargetType.ALL
    department_id: Optional[int] = None
    section: Optional[str] = None
    target_student_ids: Optional[List[int]] = None
    status: AnnouncementStatus = AnnouncementStatus.ACTIVE

class AnnouncementResponse(AnnouncementCreate):
    id: int
    created_by: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


@router.post(
    "/announcements",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED
)
def create_announcement(
    announcement: AnnouncementCreate,
    auth: AuthContext = Depends(require_faculty),
    db: Session = Depends(get_db)
):
    row = PlacementAnnouncement(
        **announcement.model_dump(),
        created_by=auth.user_id
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return row

@router.get(
    "/announcements",
    response_model=List[AnnouncementResponse]
)
def get_announcements(
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return (
        db.query(PlacementAnnouncement)
        .order_by(PlacementAnnouncement.created_at.desc())
        .all()
    )

@router.get(
    "/announcements/{announcement_id}",
    response_model=AnnouncementResponse
)
def get_announcement(
    announcement_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    row = (
        db.query(PlacementAnnouncement)
        .filter(PlacementAnnouncement.id == announcement_id)
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )

    return row