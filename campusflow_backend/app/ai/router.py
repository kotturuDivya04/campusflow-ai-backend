from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.api.deps import AuthContext, get_current_user, require_admin
from app.ai.service import AIService
from app.ai.dependencies import get_ai_service
from app.ai.schemas import (
    PriorityRequest, PriorityResponse, ChatRequest, ChatResponse,
    ChatHistoryElement, FeedbackRequest, FeedbackResponse,
    KnowledgeEntry, UploadResponse, RetrainResponse
)

logger = logging.getLogger("campusflow.ai.router")

router = APIRouter(prefix="/ai", tags=["ai"])

# --- Endpoints ---

@router.post("/priority", response_model=PriorityResponse)
async def generate_priority(
    payload: PriorityRequest,
    auth: AuthContext = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    """
    Evaluates and returns an advisory priority score and queue recommendation.
    Only accessible by authenticated users.
    """
    try:
        assessment = await ai_service.calculate_appointment_priority(
            appointment_id=payload.appointment_id,
            appointment_details=payload.appointment_details,
            student_details=payload.student_details,
            faculty_details=payload.faculty_details,
            category=payload.category,
            reason=payload.reason,
            deadline=payload.deadline,
            requested_duration=payload.requested_duration,
            previous_history=payload.previous_history,
            is_emergency=payload.is_emergency,
        )
        return PriorityResponse(
            priority_score=assessment.priority_score,
            priority_level=assessment.priority_level,
            decision_reason=assessment.decision_reason,
            recommendation=assessment.recommendation,
        )
    except Exception as e:
        logger.error(f"Failed to generate priority in router: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error processing priority calculation.")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    payload: ChatRequest,
    auth: AuthContext = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    """
    Conversational support chat. Placeholder endpoint calling AIService.chat().
    """
    try:
        result = await ai_service.chat(
            user_id=auth.user_id,
            session_id=payload.session_id,
            message=payload.message,
        )
        return ChatResponse(
            session_id=payload.session_id,
            response=result.get("response", ""),
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error processing chat request.")


@router.get("/history", response_model=list[ChatHistoryElement])
async def get_chat_history(
    session_id: str | None = None,
    auth: AuthContext = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    """
    Retrieves conversational logs. Placeholder endpoint calling AIService.get_chat_history().
    """
    try:
        history = await ai_service.get_chat_history(
            user_id=auth.user_id,
            session_id=session_id,
        )
        return [
            ChatHistoryElement(
                id=h.get("id"),
                user_id=h.get("user_id", auth.user_id),
                session_id=h.get("session_id", ""),
                message_role=h.get("message_role", ""),
                message_content=h.get("message_content", ""),
                created_at=h.get("created_at"),
            )
            for h in history
        ]
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Error in history endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error fetching chat history.")


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest,
    auth: AuthContext = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    """
    Submits user ratings/comments. Placeholder endpoint calling AIService.submit_feedback().
    """
    try:
        result = await ai_service.submit_feedback(
            chat_id=payload.chat_id,
            user_id=auth.user_id,
            rating=payload.rating,
            comment=payload.comment,
        )
        return FeedbackResponse(
            success=result.get("success", True),
            message=result.get("message", "Feedback recorded successfully."),
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Error in feedback endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error registering feedback.")


@router.get("/knowledge", response_model=list[KnowledgeEntry])
async def retrieve_knowledge_base(
    query: str,
    limit: int = 5,
    auth: AuthContext = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    """
    Fetches matching FAQ knowledge records. Placeholder endpoint calling AIService.retrieve_knowledge().
    """
    try:
        records = await ai_service.retrieve_knowledge(query=query, limit=limit)
        return [
            KnowledgeEntry(
                id=r.get("id", 0),
                title=r.get("title", ""),
                question=r.get("question", ""),
                answer=r.get("answer", ""),
                category=r.get("category", ""),
                tags=r.get("tags", []),
            )
            for r in records
        ]
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Error in knowledge endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error fetching knowledge records.")


@router.post("/admin/upload", response_model=UploadResponse)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_admin),
    ai_service: AIService = Depends(get_ai_service),
):
    """
    Uploads new document context source. Restricted to administrators.
    """
    try:
        if file.size and file.size > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 20MB.")
            
        file_content = await file.read()
        
        chunks_processed = await ai_service.process_admin_upload(
            file_content=file_content,
            filename=file.filename or "unknown",
            content_type=file.content_type or "application/octet-stream",
        )
        
        return UploadResponse(
            success=True,
            filename=file.filename or "unknown",
            message=f"Successfully processed {chunks_processed} chunks from {file.filename}"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in admin upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error uploading document.")


@router.post("/admin/retrain", response_model=RetrainResponse)
async def retrain_knowledge_index(
    auth: AuthContext = Depends(require_admin),
    ai_service: AIService = Depends(get_ai_service),
):
    """
    Triggers re-indexing of semantic vectors. Restricted to administrators. Future TODO.
    """
    try:
        # Future TODO placeholder
        raise NotImplementedError("Model retraining and indexing index refresh is not yet implemented.")
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Error in admin retrain: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error triggering index rebuild.")
