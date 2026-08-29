from __future__ import annotations

import datetime as _dt
from typing import Any

from pydantic import BaseModel, Field


# --- LLM Service Schemas ---
class LLMResponse(BaseModel):
    """Structured response model containing LLM output and metadata for logging."""
    content: str
    tokens_used: int = Field(default=0, description="Total tokens used (prompt + completion)")
    latency_ms: int = Field(default=0, description="Response latency in milliseconds")
    success: bool
    error_message: str | None = Field(default=None, description="Detailed error description if execution failed")


# --- Priority Engine Schemas ---
class PriorityAssessment(BaseModel):
    """Structured outcome of the priority assessment calculation."""
    priority_score: int = Field(description="Priority score from 0 (lowest) to 100 (highest)")
    priority_level: str = Field(description="Advisory priority level (HIGH, MEDIUM, or LOW)")
    decision_reason: str = Field(description="Explanatory rationale for the evaluation")
    recommendation: str = Field(description="Advisory queue or timing adjustments recommendation")


# --- API Request and Response Schemas ---
class PriorityRequest(BaseModel):
    appointment_id: int = Field(description="ID of the appointment being evaluated")
    appointment_details: dict[str, Any] = Field(description="Core appointment properties")
    student_details: dict[str, Any] = Field(description="Details of the student requesting booking")
    faculty_details: dict[str, Any] = Field(description="Details of the faculty member")
    category: str = Field(description="Category of the booking")
    reason: str = Field(description="Reason of the appointment")
    deadline: str | None = Field(default=None, description="Urgency milestone date/time limit")
    requested_duration: int | None = Field(default=None, description="Requested duration in minutes")
    previous_history: str | None = Field(default=None, description="Previous booking cancels/behaviors")
    is_emergency: bool = Field(default=False, description="Emergency urgency flag")


class PriorityResponse(BaseModel):
    priority_score: int
    priority_level: str
    decision_reason: str
    recommendation: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str


class ChatHistoryElement(BaseModel):
    id: int | None = None
    user_id: int
    session_id: str
    message_role: str
    message_content: str
    created_at: str | None = None


class FeedbackRequest(BaseModel):
    chat_id: int
    rating: int
    comment: str | None = None


class FeedbackResponse(BaseModel):
    success: bool
    message: str


class KnowledgeEntry(BaseModel):
    id: int
    title: str
    question: str
    answer: str
    category: str
    tags: list[str]


class UploadResponse(BaseModel):
    success: bool
    filename: str
    message: str


class RetrainResponse(BaseModel):
    success: bool
    message: str


# --- Domain Data Schemas ---
class KnowledgeBaseEntry(BaseModel):
    """Data model representing a record in the AI knowledge base."""
    id: int
    title: str
    question: str
    answer: str
    category: str
    tags: list[str] = Field(default_factory=list)
    created_at: _dt.datetime
    updated_at: _dt.datetime
