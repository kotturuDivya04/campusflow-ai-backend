from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("campusflow.ai.feedback")


class AIFeedbackService:
    """
    Service Layer responsible for managing user feedback (ratings and comments) on AI interactions.
    Validates user submissions and prepares logs for database storage.
    
    Conforms to existing backend conventions by utilizing keyword-only argument contracts.
    """

    def __init__(self, *, db_session: Any = None) -> None:
        self._db = db_session
        from app.ai.repository import AIFeedbackRepository
        self._repo = AIFeedbackRepository(session=self._db) if self._db else None

    async def submit_chat_feedback(
        self,
        *,
        chat_id: int,
        user_id: int,
        rating: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """
        Validates and registers rating and comment feedback for a given chatbot interaction.
        Returns a standardized status envelope dict.

        Args:
            chat_id: Database identifier of the specific message log (chat_history ID).
            user_id: ID of the student or faculty member submitting the rating.
            rating: Evaluation score between 1 (poor) and 5 (excellent).
            comment: Optional detailed text critique.
        """
        logger.info(f"Receiving feedback for chat ID {chat_id} from user ID {user_id}")

        # Input Validation
        if chat_id <= 0:
            raise ValueError("Invalid chat_id. Identifier must be a positive integer.")
        if user_id <= 0:
            raise ValueError("Invalid user_id. Identifier must be a positive integer.")
        if not (1 <= rating <= 5):
            raise ValueError("Feedback rating must be an integer between 1 and 5 inclusive.")

        if not self._repo:
            raise RuntimeError("Database session not initialized.")
            
        record = self._repo.create(
            chat_id=chat_id,
            user_id=user_id,
            rating=rating,
            comment=comment.strip() if comment else None,
        )
        
        if not record:
            logger.warning("Database unavailable. Feedback persistence fell back gracefully.")
            return {
                "success": False,
                "message": "Feedback could not be recorded due to database unavailability.",
            }

        logger.info(f"Feedback prepared and validated successfully. ID: {record.id}")
        return {
            "success": True,
            "message": "Feedback submitted successfully.",
            "feedback_id": record.id,
        }
