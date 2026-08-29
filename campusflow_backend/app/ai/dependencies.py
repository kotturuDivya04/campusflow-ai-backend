from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ai.llm_service import LLMService
from app.ai.priority_engine import AIPriorityEngine
from app.ai.repository import AIChatHistoryRepository
from app.ai.service import AIService


def get_ai_service(db: Session = Depends(get_db)) -> AIService:
    """
    Assembles and injects the AIService dependency.
    Wires together the LLMService, PriorityEngine, and orchestration layers.
    """
    from app.ai.feedback import AIFeedbackService
    from app.ai.repository import PriorityDecisionRepository
    from app.ai.knowledge_base import AIKnowledgeBaseService
    from app.ai.embeddings import EmbeddingService
    from app.ai.retrieval import AIRetrievalService

    llm_service = LLMService()
    priority_engine = AIPriorityEngine(llm_service=llm_service)
    chat_repo = AIChatHistoryRepository(session=db)
    feedback_service = AIFeedbackService(db_session=db)
    priority_decision_repo = PriorityDecisionRepository(session=db)
    kb_service = AIKnowledgeBaseService(db_session=db)
    embedding_service = EmbeddingService()
    retrieval_service = AIRetrievalService(
        embedding_service=embedding_service,
        knowledge_base_service=kb_service,
    )

    return AIService(
        priority_engine=priority_engine,
        ai_repository=chat_repo,
        feedback_service=feedback_service,
        priority_decision_repository=priority_decision_repo,
        knowledge_base_service=kb_service,
        embedding_service=embedding_service,
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )
