"""
Domain error catalogue. Each error carries an HTTP status so the API layer can
translate it to a meaningful response without a lookup table (brief: "return
meaningful HTTP status codes and error messages"). Adapted from the original
backend's error catalogue and trimmed to the MVP surface.
"""
from __future__ import annotations


class CampusFlowError(Exception):
    code: str = "CAMPUSFLOW_ERROR"
    http_status: int = 400

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


class NotFound(CampusFlowError):
    code = "NOT_FOUND"
    http_status = 404


class NotAuthenticated(CampusFlowError):
    code = "NOT_AUTHENTICATED"
    http_status = 401


class PermissionDenied(CampusFlowError):
    code = "PERMISSION_DENIED"
    http_status = 403


class ValidationFailed(CampusFlowError):
    code = "VALIDATION_FAILED"
    http_status = 422


class Conflict(CampusFlowError):
    code = "CONFLICT"
    http_status = 409


class DuplicateRequest(Conflict):
    code = "DUPLICATE_REQUEST"


class SlotUnavailable(Conflict):
    code = "SLOT_UNAVAILABLE"


class IllegalTransition(Conflict):
    code = "ILLEGAL_TRANSITION"
