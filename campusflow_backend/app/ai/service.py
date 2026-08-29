from __future__ import annotations

import logging
from typing import Any

from app.ai.priority_engine import AIPriorityEngine
from app.ai.schemas import PriorityAssessment

logger = logging.getLogger("campusflow.ai.service")


class AIService:
    """
    AI Service Layer that orchestrates subsystems of the Artificial Intelligence module.
    Exposes clean interfaces for priority calculations and future chatbot workflows.
    
    Conforms to existing backend service layer patterns by taking dependencies via 
    constructor injection and enforcing keyword-only argument rules.
    """

    def __init__(
        self,
        *,
        priority_engine: AIPriorityEngine,
        # Abstract placeholder for future DB operations (repository pattern)
        ai_repository: Any = None,
        feedback_service: Any = None,
        priority_decision_repository: Any = None,
        knowledge_base_service: Any = None,
        embedding_service: Any = None,
        retrieval_service: Any = None,
        llm_service: Any = None,
    ) -> None:
        self._priority = priority_engine
        self._repo = ai_repository
        self._feedback = feedback_service
        self._priority_decisions = priority_decision_repository
        self._kb_service = knowledge_base_service
        self._embedding_service = embedding_service
        self._retrieval = retrieval_service
        self._llm = llm_service

    async def calculate_appointment_priority(
        self,
        *,
        appointment_id: int,
        appointment_details: dict[str, Any],
        student_details: dict[str, Any],
        faculty_details: dict[str, Any],
        category: str,
        reason: str,
        deadline: str | None = None,
        requested_duration: int | None = None,
        previous_history: str | None = None,
        is_emergency: bool = False,
    ) -> PriorityAssessment:
        """
        Orchestrates appointment priority calculations.
        AI result is advisory only — does NOT influence deterministic scheduling.

        Args:
            appointment_id: ID of the appointment being evaluated. Required for persistence.
            appointment_details: Core parameters of the slot/date.
            student_details: Identity and registration parameters of the student.
            faculty_details: Parameters of the faculty member.
            category: Domain classification.
            reason: Plaintext justification.
            deadline: Critical milestone or target date.
            requested_duration: Estimated length of meeting.
            previous_history: History logs.
            is_emergency: Emergency flag indicator.
        """
        try:
            assessment = await self._priority.calculate_priority(
                appointment_details=appointment_details,
                student_details=student_details,
                faculty_details=faculty_details,
                category=category,
                reason=reason,
                deadline=deadline,
                requested_duration=requested_duration,
                previous_history=previous_history,
                is_emergency=is_emergency,
            )
        except Exception as e:
            logger.error(f"Error occurred during appointment priority calculation: {str(e)}")
            # Fall back to priority_engine's internal emergency-aware fallback method directly
            assessment = await self._priority.calculate_priority(
                appointment_details=appointment_details,
                student_details=student_details,
                faculty_details=faculty_details,
                category=category,
                reason=reason,
                deadline=deadline,
                requested_duration=requested_duration,
                previous_history=previous_history,
                is_emergency=is_emergency,
            )

        # Persist the advisory AI decision into priority_decisions for evaluation.
        # This does NOT affect AppointmentService or deterministic scheduling.
        if self._priority_decisions is not None:
            try:
                self._priority_decisions.log_decision(
                    appointment_id=appointment_id,
                    priority_score=assessment.priority_score,
                    decision_reason=assessment.decision_reason,
                )
            except Exception as persist_error:
                logger.warning(
                    f"Advisory priority decision persistence failed for appointment_id={appointment_id}: "
                    f"{str(persist_error)} — assessment still returned to caller."
                )

        return assessment

    async def chat(
        self,
        *,
        user_id: int,
        session_id: str,
        message: str,
    ) -> dict[str, Any]:
        """
        Chatbot orchestration with chat history persistence and live application state context.
        """
        if not self._repo or not self._llm or not self._retrieval:
            raise RuntimeError("Required services (Repository, LLM, Retrieval) are not fully initialized.")

        # 1. Persist user message
        try:
            self._repo.add_message(user_id=user_id, session_id=session_id, role="user", content=message)
        except Exception as e:
            pass

        import json
        try:
            payload = json.loads(message)
            if isinstance(payload, dict) and payload.get("context") == "club_venue_conflict":
                from app.ai.chatbot import AIChatbot
                bot = AIChatbot(retrieval_service=self._retrieval, llm_service=self._llm)
                
                # Fetch history for bot
                history = []
                try:
                    history_objs = self._repo.get_session_history(user_id=user_id, session_id=session_id)
                    history = [{"role": h.message_role, "content": h.message_content} for h in history_objs[-5:] if h.message_role in ("user", "assistant", "system")]
                except Exception:
                    pass
                
                llm_text = await bot.get_chat_response(user_query=message, chat_history=history, limit_context=3)
                
                try:
                    self._repo.add_message(user_id=user_id, session_id=session_id, role="assistant", content=llm_text)
                except Exception:
                    pass
                return {"response": llm_text, "session_id": session_id}
        except Exception:
            pass

        
        # 2. Retrieve live application state context
        live_state_context = []
        # db is assigned OUTSIDE the try so it is always reachable in the
        # except block below for rollback, even in the (very unlikely)
        # case that the attribute access itself were ever to fail.
        db = self._repo.session
        try:
            from sqlalchemy import text
            
            # Get user's appointments and queue positions
            query = text("""
                SELECT q.id, r.title, q.priority_score, q.state, q.token_number, 
                       f.first_name || ' ' || f.last_name AS faculty_name, r.scheduled_time,
                       q.priority_updated_at, q.reschedule_completed_at
                FROM queue_entries q
                JOIN requests r ON q.request_id = r.id
                JOIN users f ON q.faculty_id = f.id
                WHERE q.student_id = :uid AND q.state IN ('WAITING', 'CONFIRMED')
            """)
            queue_results = db.execute(query, {"uid": user_id}).fetchall()
            
            for row in queue_results:
                state_str = f"- Queue Entry for {row.faculty_name} (Topic: {row.title}): Priority Score is {row.priority_score}, Queue Position (Token) is #{row.token_number}, Status: {row.state}."
                if row.scheduled_time:
                    state_str += f" Scheduled Time: {row.scheduled_time}."
                if row.priority_updated_at:
                    state_str += f" Priority was re-evaluated/updated at {row.priority_updated_at}."
                if row.reschedule_completed_at:
                    state_str += f" Appointment was rescheduled at {row.reschedule_completed_at}."
                live_state_context.append(state_str)
                
            # Get user's recent swaps
            swap_query = text("""
                SELECT s.id, s.status, s.reason, s.swap_requested_at, s.swap_completed_at,
                       qr.student_id as req_student, qt.student_id as target_student
                FROM swap_requests s
                JOIN queue_entries qr ON s.requesting_queue_entry_id = qr.id
                JOIN queue_entries qt ON s.target_queue_entry_id = qt.id
                WHERE qr.student_id = :uid OR qt.student_id = :uid
                ORDER BY s.swap_requested_at DESC LIMIT 5
            """)
            swap_results = db.execute(swap_query, {"uid": user_id}).fetchall()
            
            for row in swap_results:
                role = "requested by you" if row.req_student == user_id else "requested from you"
                live_state_context.append(
                    f"- Swap Request #{row.id} ({role}): Status={row.status}, Reason='{row.reason}'. "
                    f"Requested at {row.swap_requested_at}. Completed at {row.swap_completed_at}."
                )
                
            # Get overall queue for context (who is ahead)
            if queue_results:
                for row in queue_results:
                    ahead_query = text("""
                        SELECT u.first_name || ' ' || u.last_name AS student_name,
                               q.priority_score, q.token_number, q.priority_updated_at
                        FROM queue_entries q
                        JOIN requests r ON q.request_id = r.id
                        JOIN users u ON q.student_id = u.id
                        WHERE q.faculty_id = (SELECT faculty_id FROM queue_entries WHERE id = :qid)
                          AND q.token_number < :token
                          AND q.state = 'WAITING'
                        ORDER BY q.token_number ASC
                    """)
                    ahead_results = db.execute(ahead_query, {"qid": row.id, "token": row.token_number}).fetchall()
                    for arow in ahead_results:
                        live_state_context.append(
                            f"- Student ahead in queue: {arow.student_name} (Position #{arow.token_number}, Priority {arow.priority_score}). Priority last updated: {arow.priority_updated_at}."
                        )
                        
        except Exception as e:
            import logging
            logging.error(f"Failed to fetch live context: {e}")
            # CRITICAL: this session (self._repo.session) is the SAME
            # request-scoped SQLAlchemy session shared by chat_repo,
            # kb_service (used by self._retrieval's pgvector search below),
            # and priority_decision_repo (see app/ai/dependencies.py's
            # get_ai_service). In real Postgres, one failed statement aborts
            # the whole transaction - every later statement on this session
            # (the RAG similarity search just below, and persisting the
            # assistant's reply at the end of this method) would then fail
            # with "current transaction is aborted" until rolled back.
            # Without this, one bad live-state query would silently break
            # the entire rest of the chat turn.
            try:
                db.rollback()
            except Exception as rollback_err:
                logging.error(f"Failed to rollback after live-context error: {rollback_err}")
            
        context_snippets = []
        try:
            context_snippets = await self._retrieval.retrieve_context(query=message, limit=3)
        except Exception as e:
            pass

        # 3. Construct LLM prompt
        system_content = "You are CampusFlow AI, a helpful university assistant. Answer the user's questions accurately using the provided context."
        
        full_context = ""
        if live_state_context:
            full_context += "CURRENT APPLICATION STATE (LIVE DB DATA):\n" + "\n".join(live_state_context) + "\n\n"
        if context_snippets:
            full_context += "KNOWLEDGE BASE DOCUMENTS:\n" + "\n".join(context_snippets)
            
        # Route final prompt assembly through the REAL intended pipeline
        # (ai/prompt_builder.py's build_chatbot_messages) instead of the
        # hand-rolled `messages = [...]` this method used before - that
        # bypass meant prompt_builder.py/response_engine.py/
        # conversation_manager.py were fully built but never actually used by
        # /ai/chat. This also fixes two real bugs found alongside it: no
        # prior chat-history turns were ever included, and an LLM failure
        # leaked the raw Python exception text straight into the user-facing
        # chat response instead of a graceful message.
        from app.ai.prompt_builder import build_chatbot_messages
        from app.ai.response_engine import AIResponseEngine

        history: list[dict[str, str]] = []
        try:
            history_objs = self._repo.get_session_history(user_id=user_id, session_id=session_id)
            history = [
                {"role": h.message_role, "content": h.message_content}
                for h in history_objs[-5:] if h.message_role in ("user", "assistant", "system")
            ]
        except Exception as e:
            logger.warning(f"Could not retrieve chat history: {e}")

        combined_context: list[str] = []
        if live_state_context:
            combined_context.append(
                "CURRENT APPLICATION STATE (LIVE DB DATA):\n" + "\n".join(live_state_context))
        if context_snippets:
            combined_context.extend(context_snippets)

        messages = build_chatbot_messages(
            user_query=message, context_snippets=combined_context, chat_history=history,
        )

        try:
            response = await self._llm.generate_response(messages=messages)
            if response.success and response.content:
                llm_text = response.content
            else:
                logger.error(f"LLM generate_response returned success=False: {response.error_message}")
                llm_text = (
                    "I'm sorry, I am currently experiencing connection difficulties reaching my "
                    "AI service. Please try asking your campus scheduling or timetable question "
                    "again in a moment."
                )
        except Exception as e:
            logger.error(f"LLM call execution failed: {e}")
            llm_text = (
                "I'm sorry, I am currently experiencing connection difficulties reaching my "
                "AI service. Please try asking your campus scheduling or timetable question "
                "again in a moment."
            )

        llm_text = AIResponseEngine().clean_text(text=llm_text)

        try:
            self._repo.add_message(user_id=user_id, session_id=session_id, role="assistant", content=llm_text)
        except Exception as e:
            pass
            
        return {
            "response": llm_text,
            "session_id": session_id
        }

    async def get_chat_history(
        self,
        *,
        user_id: int,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieves user conversation histories from database.
        """
        if not session_id:
            return []
            
        history = self._repo.get_session_history(user_id=user_id, session_id=session_id)
        return [
            {
                "id": h.id,
                "user_id": h.user_id,
                "session_id": h.session_id,
                "message_role": h.message_role,
                "message_content": h.message_content,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in history
        ]

    async def submit_feedback(
        self,
        *,
        chat_id: int,
        user_id: int,
        rating: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """
        Stores user ratings/comments on chatbot logs.
        """
        if not self._feedback:
            raise RuntimeError("Feedback service not initialized.")
            
        return await self._feedback.submit_chat_feedback(
            chat_id=chat_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
        )

    async def retrieve_knowledge(
        self,
        *,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        RAG document retrieval and search matching.
        """
        if not self._kb_service or not self._embedding_service or not hasattr(self._kb_service, '_repo') or not self._kb_service._repo:
            raise RuntimeError("Knowledge base or Embedding Service not initialized.")
            
        query_vector = await self._embedding_service.get_embedding(text=query)
        if getattr(self._embedding_service, "last_call_used_fallback", False):
            return []
            
        records = self._kb_service._repo.search_similar_entries(query_vector=query_vector, limit=limit)
        
        return [
            {
                "id": r.id,
                "title": r.title,
                "question": r.question,
                "answer": r.answer,
                "category": r.category,
                "tags": r.tags.split(",") if r.tags else []
            }
            for r in records
        ]

    async def process_admin_upload(
        self,
        *,
        file_content: bytes,
        filename: str,
        content_type: str,
    ) -> int:
        """
        Coordinates the extraction, chunking, and persistence of uploaded documents.
        """
        if not self._kb_service or not self._embedding_service:
            raise RuntimeError("Knowledge Base or Embedding Service not initialized.")
            
        return await self._kb_service.process_upload(
            file_content=file_content,
            filename=filename,
            content_type=content_type,
            embedding_service=self._embedding_service
        )
