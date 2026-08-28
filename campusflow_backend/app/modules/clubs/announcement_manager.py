"""Announcement workflows for the Clubs module."""
from __future__ import annotations

from app.core.errors import NotFound, ValidationFailed
from app.modules.clubs.constants import ANNOUNCEMENT_TARGETS, DEFAULT_ANNOUNCEMENT_TARGET
from app.modules.clubs.models import Announcement
from app.modules.clubs.repository import AnnouncementRepository, ClubRepository


class AnnouncementManager:
    def __init__(
        self,
        announcement_repo: AnnouncementRepository,
        club_repo: ClubRepository,
    ) -> None:
        self._announcements = announcement_repo
        self._clubs = club_repo

    def _validate_club(self, club_id: int) -> None:
        if self._clubs.by_id(club_id) is None:
            raise NotFound(f"club {club_id} not found")

    def _validate_target(self, target: str) -> str:
        resolved = target or DEFAULT_ANNOUNCEMENT_TARGET
        if resolved not in ANNOUNCEMENT_TARGETS:
            raise ValidationFailed(f"invalid announcement target '{resolved}'")
        return resolved

    def create_announcement(self, payload: dict) -> Announcement:
        self._validate_club(payload["club_id"])
        payload["target"] = self._validate_target(payload.get("target", DEFAULT_ANNOUNCEMENT_TARGET))
        payload["is_published"] = payload.get("is_published", False)
        return self._announcements.create(**payload)

    def update_announcement(self, announcement_id: int, payload: dict) -> Announcement:
        announcement = self._announcements.by_id(announcement_id)
        if announcement is None:
            raise NotFound(f"announcement {announcement_id} not found")
        if payload.get("target") is not None:
            payload["target"] = self._validate_target(payload["target"])
        if payload.get("is_published") and announcement.published_at is None:
            announcement.published_at = announcement.updated_at
        return self._announcements.update(announcement, **payload)

    def delete_announcement(self, announcement_id: int) -> None:
        announcement = self._announcements.by_id(announcement_id)
        if announcement is None:
            raise NotFound(f"announcement {announcement_id} not found")
        self._announcements.delete(announcement)

    def list_announcements(self, limit: int = 50, offset: int = 0) -> list[Announcement]:
        return self._announcements.list(limit=limit, offset=offset)

    def list_for_club(self, club_id: int, limit: int = 50, offset: int = 0) -> list[Announcement]:
        self._validate_club(club_id)
        return self._announcements.list_for_club(club_id, limit=limit, offset=offset)
