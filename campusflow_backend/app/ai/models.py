import datetime as _dt
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base

# Note: pgvector is required by AI architecture. 
# Once installed by backend team, this can be imported:
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy import Text
    Vector = lambda *args: Text


class AIKnowledgeBase(Base):
    __tablename__ = "ai_knowledge_base"

    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(100), index=True)
    tags = Column(String(255)) # Storing tags as CSV or JSON string for simplicity
    
    # Required pgvector embedding column. Changed to 1024 to support NVIDIA nvidia/nv-embedqa-e5-v5
    embedding_vector = Column(Vector(2048))
    
    created_at = Column(DateTime, default=_dt.datetime.utcnow)
    updated_at = Column(DateTime, default=_dt.datetime.utcnow, onupdate=_dt.datetime.utcnow)


class AIChatHistory(Base):
    __tablename__ = "ai_chat_history"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    session_id = Column(String(255), index=True, nullable=False)
    message_role = Column(String(50), nullable=False) # 'user', 'assistant', 'system'
    message_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_dt.datetime.utcnow)


class AIFeedback(Base):
    __tablename__ = "ai_feedback"

    id = Column(BigInteger, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("ai_chat_history.id"), nullable=False)
    user_id = Column(BigInteger, nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_dt.datetime.utcnow)


class PriorityDecision(Base):
    __tablename__ = "priority_decisions"

    id = Column(BigInteger, primary_key=True, index=True)
    appointment_id = Column(BigInteger, index=True, nullable=False)
    priority_score = Column(Integer, nullable=False)
    decision_reason = Column(Text, nullable=False)
    engine_used = Column(String(100), default="AIPriorityEngine_v1")
    created_at = Column(DateTime, default=_dt.datetime.utcnow)
