from __future__ import annotations

import logging
import json
from typing import Any

from app.ai.llm_service import LLMService
from app.ai.prompt_builder import build_chatbot_messages, build_club_venue_conflict_messages
from app.ai.retrieval import AIRetrievalService

logger = logging.getLogger("campusflow.ai.chatbot")


class AIChatbot:
    """
    Chatbot Orchestrator that coordinates context retrieval, message building, 
    and LLM invocation. Does not format answers or commit data directly.
    """

    def __init__(
        self,
        *,
        retrieval_service: AIRetrievalService,
        llm_service: LLMService,
    ) -> None:
        self._retrieval = retrieval_service
        self._llm = llm_service

    async def get_chat_response(
        self,
        *,
        user_query: str,
        chat_history: list[dict[str, str]] | None = None,
        limit_context: int = 3,
    ) -> str:
        """
        Retrieves context, formats messages, and queries the LLM for a raw response string.
        """
        # Try to detect special payloads like club_venue_conflict
        try:
            logger.info(f'USER QUERY IS: {user_query}')
            open('/tmp/debug.txt', 'a').write(f'USER QUERY: {repr(user_query)}\n')
            payload = json.loads(user_query)
            if isinstance(payload, dict) and payload.get("context") == "club_venue_conflict":
                return await self._handle_club_venue_conflict(payload, limit_context)
        except json.JSONDecodeError:
            pass

        # Step 1: Retrieve relevant context snippets using RAG
        context_snippets: list[str] = []
        try:
            context_snippets = await self._retrieval.retrieve_context(query=user_query, limit=limit_context)
        except Exception as e:
            logger.error(f"AIRetrievalService context extraction failed: {str(e)}")

        # Step 2: Format prompt messages using PromptBuilder
        try:
            messages = build_chatbot_messages(
                user_query=user_query,
                context_snippets=context_snippets,
                chat_history=chat_history,
            )
        except Exception as e:
            logger.error(f"Prompt building failed: {str(e)}")
            messages = [
                {"role": "system", "content": "You are the CampusFlow AI Chatbot assistant."},
                {"role": "user", "content": user_query}
            ]

        # Step 3: Call the pluggable LLM Service
        try:
            llm_response = await self._llm.generate_response(messages=messages, temperature=0.7)
            if llm_response.success and llm_response.content:
                return llm_response.content
            
            err_msg = llm_response.error_message or "Unknown LLM failure."
            logger.error(f"LLM generate_response returned success=False: {err_msg}")
        except Exception as e:
            logger.error(f"LLM call execution failed: {str(e)}")

        # Step 4: Graceful fallback response if LLM was unreachable
        return (
            "I'm sorry, I am currently experiencing connection difficulties reaching my AI service. "
            "Please try asking your campus scheduling or timetable question again in a moment."
        )

    async def _handle_club_venue_conflict(self, payload: dict[str, Any], limit_context: int) -> str:
        fallback_response = {
            "recommendations": [],
            "summary": "AI recommendations are temporarily unavailable. Please choose from the verified available alternatives."
        }
        fallback_json = json.dumps(fallback_response)

        try:
            # Optionally use RAG for venue characteristics
            search_query = f"venue {payload.get('requested_venue')} {payload.get('event_title')} {payload.get('event_description')}"
            context_snippets: list[str] = []
            try:
                context_snippets = await self._retrieval.retrieve_context(query=search_query, limit=limit_context)
            except Exception as e:
                logger.error(f"RAG failed for venue conflict: {str(e)}")

            available_alternatives = payload.get("available_alternatives", [])
            if not available_alternatives:
                return json.dumps({
                    "recommendations": [],
                    "summary": "No available alternatives provided."
                })

            messages = build_club_venue_conflict_messages(
                event_title=payload.get("event_title", ""),
                event_description=payload.get("event_description", ""),
                requested_date=payload.get("requested_date", ""),
                requested_start_time=payload.get("requested_start_time", ""),
                requested_end_time=payload.get("requested_end_time", ""),
                requested_venue=payload.get("requested_venue", ""),
                conflict_reason=payload.get("conflict_reason", ""),
                available_alternatives=available_alternatives,
                context_snippets=context_snippets,
            )

            llm_response = await self._llm.generate_response(messages=messages, temperature=0.2)
            if not llm_response.success or not llm_response.content:
                return fallback_json

            # Validate the JSON
            try:
                result = json.loads(llm_response.content)
            except json.JSONDecodeError:
                # If LLM returned bad JSON
                return fallback_json

            recommendations = result.get("recommendations", [])
            valid_recommendations = []
            
            # Validation: filter out invented venues/times
            for rec in recommendations:
                if not isinstance(rec, dict):
                    continue
                v = rec.get("venue")
                st = rec.get("start_time")
                et = rec.get("end_time")
                reason = rec.get("reason")

                if not v or not st or not et or not reason:
                    continue
                
                # Check if matches exactly one of the alternatives
                match = any(
                    alt.get("venue") == v and alt.get("start_time") == st and alt.get("end_time") == et
                    for alt in available_alternatives
                )
                if match:
                    valid_recommendations.append(rec)
            
            result["recommendations"] = valid_recommendations
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Club venue conflict handling failed: {str(e)}")
            return fallback_json
