from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.llm_service import LLMService
from app.ai.prompt_builder import build_priority_messages
from app.ai.schemas import PriorityAssessment

logger = logging.getLogger("campusflow.ai.priority_engine")


class AIPriorityEngine:
    """
    Evaluates and calculates appointment priorities using LLM capabilities.
    Does not interact with the database directly.
    """

    def __init__(self, *, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or LLMService()

    async def calculate_priority(
        self,
        *,
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
        Asynchronously computes an advisory priority score, level, reasoning, and queue recommendation.
        Utilizes prompt_builder to shape the prompt and llm_service to evaluate it.
        Falls back gracefully if the model is unreachable.

        Args:
            appointment_details: Dictionary containing core appointment properties.
            student_details: Dictionary of student details.
            faculty_details: Dictionary of faculty details (e.g. teaching load, etc.).
            category: Classification of the appointment (e.g. academic, administrative).
            reason: Plaintext explanation for requesting the meeting.
            deadline: Optional target deadline or milestone limit.
            requested_duration: Expected meeting duration in minutes.
            previous_history: Optional description of previous academic or cancel behavior.
            is_emergency: Emergency flag indicator.
        """
        # Consolidate details block for building the prompt context
        combined_details = {
            "Category": category,
            "Student Name": student_details.get("name", "Unknown"),
            "Student ID": student_details.get("id", "Unknown"),
            "Faculty Name": faculty_details.get("name", "Unknown"),
            "Faculty ID": faculty_details.get("id", "Unknown"),
            **appointment_details
        }

        # Build prompt messages
        messages = build_priority_messages(
            appointment_details=combined_details,
            reason=reason,
            deadline=deadline,
            meeting_duration_minutes=requested_duration,
            student_history=previous_history,
            faculty_availability=faculty_details.get("availability_summary"),
            is_emergency=is_emergency,
        )

        # Call the pluggable LLM provider (lower temperature for deterministic outputs)
        llm_response = await self._llm.generate_response(messages=messages, temperature=0.2)

        if llm_response.success and llm_response.content:
            try:
                # Standardize potential Markdown JSON block wrappings
                raw_json = llm_response.content.strip()
                if raw_json.startswith("```"):
                    lines = raw_json.splitlines()
                    if len(lines) > 1 and lines[0].startswith("```"):
                        lines = lines[1:]
                    if len(lines) > 0 and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_json = "\n".join(lines).strip()

                parsed = json.loads(raw_json)

                # Extract and clamp the priority score
                raw_score = parsed.get("priority_score")
                if raw_score is None:
                    raw_score = 50
                score = max(0, min(100, int(raw_score)))

                # Map level strictly from the final score
                if score >= 70:
                    level = "HIGH"
                elif score >= 30:
                    level = "MEDIUM"
                else:
                    level = "LOW"

                reason_str = parsed.get("decision_reason", "AI calculated priority score successfully.")
                rec_str = parsed.get("recommendation", "Confirm and place into the standard queue.")

                return PriorityAssessment(
                    priority_score=score,
                    priority_level=level,
                    decision_reason=reason_str,
                    recommendation=rec_str,
                )
            except Exception as e:
                logger.error(
                    f"Priority Engine failed to parse LLM response: {str(e)}. "
                    f"Raw Content: {llm_response.content}"
                )

        # Graceful Fallback Strategy if LLM fails
        fallback_score = 50
        if is_emergency:
            fallback_score = 90

        if fallback_score >= 70:
            fallback_level = "HIGH"
        elif fallback_score >= 30:
            fallback_level = "MEDIUM"
        else:
            fallback_level = "LOW"

        fallback_reason = "System fallback priority assigned due to LLM service unavailability."
        if is_emergency:
            fallback_reason += " Escalated to HIGH automatically because the request was flagged as an Emergency."

        return PriorityAssessment(
            priority_score=fallback_score,
            priority_level=fallback_level,
            decision_reason=fallback_reason,
            recommendation="Review the appointment details and manually confirm the queue order.",
        )
