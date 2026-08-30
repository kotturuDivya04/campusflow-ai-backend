from __future__ import annotations

from typing import Any


def build_priority_messages(
    *,
    appointment_details: dict[str, Any],
    reason: str,
    deadline: str | None = None,
    meeting_duration_minutes: int | None = None,
    student_history: str | None = None,
    faculty_availability: str | None = None,
    is_emergency: bool = False,
) -> list[dict[str, str]]:
    """
    Constructs a structured message sequence for the AI Priority Engine.
    Instructs the LLM to output a JSON string containing the priority assessment.

    Args:
        appointment_details: Dictionary containing student info, slot info, and dates.
        reason: Plain-text explanation of why the appointment is needed.
        deadline: Date/time constraints or milestones if applicable.
        meeting_duration_minutes: Estimated duration in minutes.
        student_history: String summary of the student's booking history/conduct.
        faculty_availability: Summary of the faculty member's teaching load or bookings.
        is_emergency: Boolean flag forcing high urgency evaluation.

    Returns:
        List of message dictionaries ready for LLM consumption.
    """
    system_instruction = (
        "You are the CampusFlow AI Priority Engine.\n"
        "Your task is to analyze appointment requests and calculate their queue priority scores.\n"
        "Assess details such as emergency status, urgency reasons, scheduling deadlines, and history.\n"
        "You MUST respond ONLY in valid JSON format matching this schema:\n"
        "{\n"
        '  "priority_score": <int between 0 and 100 where higher is more urgent>,\n'
        '  "decision_reason": "<clear explanation of why this priority score was assigned>",\n'
        '  "estimated_waiting_time_minutes": <int estimated delay, or null if uncertain>,\n'
        '  "recommendation": "<advisory recommendation for queue order adjustment>"\n'
        "}"
    )

    details_block = []
    for k, v in appointment_details.items():
        details_block.append(f"- {k}: {v}")
    appointment_details_str = "\n".join(details_block)

    user_prompt = (
        "Analyze the following appointment details to assign a priority:\n\n"
        f"**Appointment Info**:\n{appointment_details_str}\n\n"
        f"**Reason for Appointment**:\n{reason}\n\n"
        f"**Urgency / Deadline Constraints**:\n{deadline or 'None specified'}\n\n"
        f"**Meeting Duration**: {meeting_duration_minutes or 'Default'} minutes\n\n"
        f"**Student Booking History**:\n{student_history or 'No negative history'}\n\n"
        f"**Faculty Daily Load / Availability**:\n{faculty_availability or 'Available'}\n\n"
        f"**Marked as Emergency**: {'YES (High Priority candidate)' if is_emergency else 'NO'}\n"
    )

    return [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_prompt},
    ]


def build_chatbot_messages(
    *,
    user_query: str,
    context_snippets: list[str] | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """
    Assembles prompt messages for the conversational AI Chatbot.
    Injects context snippets (RAG) and historical turns securely.

    Args:
        user_query: The current question asked by the student/faculty.
        context_snippets: List of text chunks retrieved from FAQ/knowledge bases.
        chat_history: Historical dialog roles and contents.

    Returns:
        List of message dictionaries ready for LLM consumption.
    """
    context_text = ""
    if context_snippets:
        context_text = "\n".join(f"- {snippet}" for snippet in context_snippets)
    else:
        context_text = "No additional context snippets retrieved for this query."

    system_instruction = (
        "You are the CampusFlow AI Chatbot.\n"
        "Your role is to provide conversational assistance throughout the application.\n"
        "You help users with appointment queries, token statuses, faculty availability,\n"
        "club schedules, campus FAQ, semester calendars, and general support.\n\n"
        "Guideline: Answer the user's question politely and concisely. If context snippets are provided below,\n"
        "prioritize that facts-based context to resolve their query. If the provided context is not enough,\n"
        "use general college policy but state clearly that it is general advice.\n\n"
        f"--- CONTEXT SNIPPETS ---\n{context_text}\n-------------------------"
    )

    messages = [{"role": "system", "content": system_instruction}]

    # Append historical turns if present
    if chat_history:
        for turn in chat_history:
            role = turn.get("role")
            content = turn.get("content")
            if role and content:
                messages.append({"role": role, "content": content})

    # Append current user prompt
    messages.append({"role": "user", "content": user_query})

    return messages

import json

def build_club_venue_conflict_messages(
    *,
    event_title: str,
    event_description: str,
    requested_date: str,
    requested_start_time: str,
    requested_end_time: str,
    requested_venue: str,
    conflict_reason: str,
    available_alternatives: list[dict[str, Any]],
    context_snippets: list[str] | None = None,
) -> list[dict[str, str]]:
    """
    Constructs a structured message sequence for the Club AI Venue Conflict Recommendation task.
    Instructs the LLM to output a strictly formatted JSON string with venue recommendations.
    """
    
    context_text = ""
    if context_snippets:
        context_text = "\n".join(f"- {snippet}" for snippet in context_snippets)
    
    system_instruction = (
        "You are the CampusFlow AI Venue Recommendation Assistant.\n"
        "Your task is to recommend the best alternative venues for a club event when the requested venue is unavailable.\n"
        "CRITICAL RULES:\n"
        "1. This is a venue conflict recommendation task.\n"
        "2. Venue availability has already been verified externally.\n"
        "3. The supplied alternatives below are the ONLY valid options.\n"
        "4. NEVER invent another venue. NEVER invent another time.\n"
        "5. Rank the alternatives according to suitability for the event, capacity, requested time, event description, and venue characteristics.\n"
        "6. Return ONLY valid JSON format matching this exact schema:\n"
        "{\n"
        '  "recommendations": [\n'
        '    {\n'
        '      "venue": "<must EXACTLY match one of the supplied alternative venues>",\n'
        '      "start_time": "<must EXACTLY match the alternative start_time>",\n'
        '      "end_time": "<must EXACTLY match the alternative end_time>",\n'
        '      "reason": "<concise reason why this is recommended>"\n'
        '    }\n'
        '  ],\n'
        '  "summary": "<brief summary of your recommendations>"\n'
        "}\n"
    )

    if context_text:
        system_instruction += f"\nCampus Knowledge (Use for context, but NEVER override availability):\n{context_text}\n"

    alternatives_json = json.dumps(available_alternatives, indent=2)

    user_message = (
        f"Event Title: {event_title}\n"
        f"Description: {event_description}\n"
        f"Requested Date: {requested_date}\n"
        f"Requested Venue: {requested_venue} ({requested_start_time} - {requested_end_time})\n"
        f"Conflict Reason: {conflict_reason}\n\n"
        f"AVAILABLE ALTERNATIVES (You MUST ONLY choose from these):\n"
        f"{alternatives_json}\n"
    )

    return [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_message}
    ]
