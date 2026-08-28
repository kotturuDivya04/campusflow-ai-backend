"""Permissions helpers for the Clubs module."""
from __future__ import annotations

from fastapi import Depends

from app.api.deps import AuthContext, get_current_user
from app.core.enums import Role
from app.core.errors import PermissionDenied


def require_club_coordinator(
    auth: AuthContext = Depends(get_current_user),
) -> AuthContext:
    if not auth.has(Role.CLUB_LEAD, Role.SUPER_ADMIN, Role.DEPARTMENT_ADMIN):
        raise PermissionDenied("club coordinator or admin access required")
    return auth


def require_event_manager(
    auth: AuthContext = Depends(get_current_user),
) -> AuthContext:
    if not auth.has(Role.FACULTY, Role.CLUB_LEAD, Role.SUPER_ADMIN, Role.DEPARTMENT_ADMIN):
        raise PermissionDenied("faculty, club lead, or admin access required")
    return auth


def require_registration_user(
    auth: AuthContext = Depends(get_current_user),
) -> AuthContext:
    if not auth.has(Role.STUDENT):
        raise PermissionDenied("student access required")
    return auth


def require_attendance_manager(
    auth: AuthContext = Depends(get_current_user),
) -> AuthContext:
    if not auth.has(Role.FACULTY, Role.SUPER_ADMIN, Role.DEPARTMENT_ADMIN):
        raise PermissionDenied("faculty or admin access required")
    return auth


def require_announcement_manager(
    auth: AuthContext = Depends(get_current_user),
) -> AuthContext:
    if not auth.has(Role.FACULTY, Role.CLUB_LEAD, Role.SUPER_ADMIN, Role.DEPARTMENT_ADMIN):
        raise PermissionDenied("faculty, club lead, or admin access required")
    return auth