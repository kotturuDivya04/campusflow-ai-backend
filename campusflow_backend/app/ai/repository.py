from typing import Any, List, Optional
from sqlalchemy.orm import Session

from app.ai.models import AIKnowledgeBase, AIChatHistory, AIFeedback, PriorityDecision


class AIKnowledgeBaseRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, title: str, question: str, answer: str, category: str, tags: str, embedding_vector: Optional[List[float]] = None) -> AIKnowledgeBase:
        entry = AIKnowledgeBase(
            title=title,
            question=question,
            answer=answer,
            category=category,
            tags=tags,
            embedding_vector=embedding_vector
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def get_by_id(self, entry_id: int) -> Optional[AIKnowledgeBase]:
        return self.session.query(AIKnowledgeBase).filter(AIKnowledgeBase.id == entry_id).first()

    def update(
        self,
        entry_id: int,
        title: Optional[str] = None,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[str] = None
    ) -> Optional[AIKnowledgeBase]:
        entry = self.get_by_id(entry_id)
        if not entry:
            return None
        if title is not None:
            entry.title = title
        if question is not None:
            entry.question = question
        if answer is not None:
            entry.answer = answer
        if category is not None:
            entry.category = category
        if tags is not None:
            entry.tags = tags
            
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def delete(self, entry_id: int) -> bool:
        entry = self.get_by_id(entry_id)
        if not entry:
            return False
        self.session.delete(entry)
        self.session.commit()
        return True

    def list_entries(self, category: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[AIKnowledgeBase]:
        query = self.session.query(AIKnowledgeBase)
        if category:
            query = query.filter(AIKnowledgeBase.category == category)
        return query.offset(offset).limit(limit).all()

    def search_similar_entries(self, query_vector: list[float], limit: int = 3) -> List[AIKnowledgeBase]:
        from sqlalchemy.exc import OperationalError, ProgrammingError
        try:
            return self.session.query(AIKnowledgeBase)\
                .order_by(AIKnowledgeBase.embedding_vector.l2_distance(query_vector))\
                .limit(limit)\
                .all()
        except Exception as e:
            import logging
            logging.error(f'Repo Error: {e}')
            self.session.rollback()
            return []


class AIChatHistoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_message(self, user_id: int, session_id: str, role: str, content: str) -> Optional[AIChatHistory]:
        from sqlalchemy.exc import OperationalError, ProgrammingError
        try:
            message = AIChatHistory(
                user_id=user_id,
                session_id=session_id,
                message_role=role,
                message_content=content
            )
            self.session.add(message)
            self.session.commit()
            self.session.refresh(message)
            return message
        except Exception as e:
            import logging
            logging.error(f'Repo Error: {e}')
            self.session.rollback()
            return None

    def get_session_history(self, user_id: int, session_id: str) -> List[AIChatHistory]:
        from sqlalchemy.exc import OperationalError, ProgrammingError
        try:
            return self.session.query(AIChatHistory)\
                .filter(AIChatHistory.user_id == user_id, AIChatHistory.session_id == session_id)\
                .order_by(AIChatHistory.created_at.asc())\
                .all()
        except Exception as e:
            import logging
            logging.error(f'Repo Error: {e}')
            self.session.rollback()
            return []


class AIFeedbackRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, chat_id: int, user_id: int, rating: int, comment: Optional[str] = None) -> Optional[AIFeedback]:
        from sqlalchemy.exc import OperationalError, ProgrammingError
        try:
            feedback = AIFeedback(
                chat_id=chat_id,
                user_id=user_id,
                rating=rating,
                comment=comment
            )
            self.session.add(feedback)
            self.session.commit()
            self.session.refresh(feedback)
            return feedback
        except Exception as e:
            import logging
            logging.error(f'Repo Error: {e}')
            self.session.rollback()
            return None


class PriorityDecisionRepository:
    def __init__(self, session: Session):
        self.session = session

    def log_decision(self, appointment_id: int, priority_score: int, decision_reason: str) -> PriorityDecision:
        decision = PriorityDecision(
            appointment_id=appointment_id,
            priority_score=priority_score,
            decision_reason=decision_reason
        )
        self.session.add(decision)
        self.session.commit()
        self.session.refresh(decision)
        return decision
