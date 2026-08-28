"""
TokenService — generates the canonical access token that the schema *does*
support, and is used by the appointment service when an approval creates a queue
entry.

Two distinct notions of "token" exist and must not be confused:

  * ACCESS TOKEN  -> a real row in the canonical `tokens` table with
    token_type = 'REQUEST_ACCESS'. It grants the student access to their
    approved request/queue entry and carries an expiry. This is what the schema
    models.
  * QUEUE TOKEN NUMBER -> the small integer position a student holds in a
    faculty's dated slot queue. There is no schema column for it, so it lives on
    the additive queue_entries.token_number (allocated by QueueRepository).

This service owns the first; the queue/appointment services own the second.
"""
from __future__ import annotations

import datetime as _dt
import secrets

from app.core.enums import TokenType
from app.repositories.repositories import TokenRepository


class TokenService:
    def __init__(self, tokens: TokenRepository) -> None:
        self._tokens = tokens

    def issue_request_access(self, *, user_id: int, ttl_hours: int = 24):
        """Create a REQUEST_ACCESS token row and return it."""
        now = _dt.datetime.now(_dt.timezone.utc)
        token = self._tokens.create(
            user_id=user_id,
            token_value=secrets.token_urlsafe(32),
            token_type=TokenType.REQUEST_ACCESS.value,
            expires_at=now + _dt.timedelta(hours=ttl_hours),
            is_active=True,
        )
        return token
