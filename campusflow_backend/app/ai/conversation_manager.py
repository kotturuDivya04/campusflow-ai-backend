from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("campusflow.ai.conversation_manager")


class AIConversationManager:
    """
    Service Layer responsible for managing and preparing chatbot conversation session states.
    Utilizes in-memory structures as developer fallback and maps placeholders for 
    the ai_chat_history database repository.
    
    Conforms to existing backend conventions by utilizing keyword-only argument contracts.
    """

    def __init__(self, *, db_session: Any = None) -> None:
        self._db = db_session
        from app.ai.repository import AIChatHistoryRepository
        self._repo = AIChatHistoryRepository(session=self._db) if self._db else None

    async def load_session(
        self,
        *,
        user_id: int,
        session_id: str,
    ) -> list[dict[str, str]]:
        """
        Loads the history of an active conversation session, formatted for prompt builder.
        
        Args:
            user_id: ID of the student or faculty member.
            session_id: Unique uuid or session key.
        """
        logger.info(f"Loading conversation session: '{session_id}' for user_id: {user_id}")

        if not self._repo:
            return []
            
        history_rows = self._repo.get_session_history(user_id=user_id, session_id=session_id)
        return [{"role": row.message_role, "content": row.message_content} for row in history_rows]

    async def append_message(
        self,
        *,
        user_id: int,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """
        Appends a new turn (role and message) to the chat session history.

        Args:
            user_id: ID of the message author.
            session_id: Unique uuid or session key.
            role: Must be 'user', 'assistant', or 'system'.
            content: Text payload of the conversation message.
        """
        logger.info(f"Appending '{role}' message to session: '{session_id}' for user_id: {user_id}")

        role = role.lower().strip()
        if role not in ("user", "assistant", "system"):
            logger.warning(f"Attempted to append invalid message role: '{role}'. Defaulting to 'user'.")
            role = "user"

        if not self._repo:
            return
            
        self._repo.add_message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content
        )

    async def get_history_list(
        self,
        *,
        user_id: int,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieves conversational history records, formatted for JSON router responses.
        
        Args:
            user_id: ID of the user requesting logs.
            session_id: Optional filter for a specific session.
        """
        logger.info(f"Retrieving session logs list for user_id: {user_id} (session_id={session_id})")

        if not self._repo or not session_id:
            return []
            
        history_rows = self._repo.get_session_history(user_id=user_id, session_id=session_id)
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "session_id": row.session_id,
                "message_role": row.message_role,
                "message_content": row.message_content,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in history_rows
        ]

    async def clear_session(
        self,
        *,
        user_id: int,
        session_id: str,
    ) -> None:
        """
        Clears memory caches for a session.

        Args:
            user_id: ID of the user author.
            session_id: Unique uuid or session key.
        """
        logger.info(f"Clearing conversation session: '{session_id}' for user_id: {user_id}")
        
        # Session deletion is not currently supported by the repository pattern.
        pass
