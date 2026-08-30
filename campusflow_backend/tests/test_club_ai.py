import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.ai.chatbot import AIChatbot
from app.ai.llm_service import LLMService
from app.ai.schemas import LLMResponse
from app.ai.retrieval import AIRetrievalService
from app.ai.prompt_builder import build_club_venue_conflict_messages

# Test 1: Normal chatbot message still works.
@pytest.mark.asyncio
async def test_normal_chatbot_message():
    retrieval = MagicMock(spec=AIRetrievalService)
    retrieval.retrieve_context = AsyncMock(return_value=["snippet1"])
    llm = MagicMock(spec=LLMService)
    llm.generate_response = AsyncMock(return_value=LLMResponse(success=True, content="Hello there", tokens_used=10, latency_ms=100))
    
    bot = AIChatbot(retrieval_service=retrieval, llm_service=llm)
    resp = await bot.get_chat_response(user_query="Hello AI")
    assert resp == "Hello there"
    # Should use normal prompt
    call_args = llm.generate_response.call_args[1]["messages"]
    assert call_args[0]["role"] == "system"
    assert "Venue Recommendation Assistant" not in call_args[0]["content"]


# Test 2: Valid club_venue_conflict payload returns structured JSON.
# Test 3: Only supplied alternatives are recommended.
@pytest.mark.asyncio
async def test_club_venue_conflict_valid():
    retrieval = MagicMock(spec=AIRetrievalService)
    retrieval.retrieve_context = AsyncMock(return_value=["snippet_venue"])
    llm = MagicMock(spec=LLMService)
    
    mock_json = {
        "recommendations": [
            {
                "venue": "Auditorium",
                "start_time": "14:00",
                "end_time": "16:00",
                "reason": "Large enough"
            }
        ],
        "summary": "Try Auditorium"
    }
    
    llm.generate_response = AsyncMock(return_value=LLMResponse(success=True, content=json.dumps(mock_json), tokens_used=10, latency_ms=100))
    
    bot = AIChatbot(retrieval_service=retrieval, llm_service=llm)
    
    payload = {
        "context": "club_venue_conflict",
        "event_title": "AI Workshop",
        "requested_venue": "Seminar Hall",
        "available_alternatives": [
            {
                "venue": "Auditorium",
                "start_time": "14:00",
                "end_time": "16:00",
                "capacity": 300
            }
        ]
    }
    
    resp = await bot.get_chat_response(user_query=json.dumps(payload))
    resp_dict = json.loads(resp)
    assert len(resp_dict["recommendations"]) == 1
    assert resp_dict["recommendations"][0]["venue"] == "Auditorium"
    assert "summary" in resp_dict


# Test 4: LLM attempts to invent a venue.
# Test 5: LLM attempts to invent a time.
@pytest.mark.asyncio
async def test_club_venue_conflict_invented():
    retrieval = MagicMock(spec=AIRetrievalService)
    retrieval.retrieve_context = AsyncMock(return_value=[])
    llm = MagicMock(spec=LLMService)
    
    # LLM invents a venue and invents a time
    mock_json = {
        "recommendations": [
            {
                "venue": "Auditorium",
                "start_time": "14:00",
                "end_time": "16:00",
                "reason": "Good"
            },
            {
                "venue": "Invented Hall",
                "start_time": "14:00",
                "end_time": "16:00",
                "reason": "Made up"
            },
            {
                "venue": "Auditorium",
                "start_time": "18:00",
                "end_time": "20:00",
                "reason": "Invented time"
            }
        ],
        "summary": "Try these"
    }
    
    llm.generate_response = AsyncMock(return_value=LLMResponse(success=True, content=json.dumps(mock_json), tokens_used=10, latency_ms=100))
    bot = AIChatbot(retrieval_service=retrieval, llm_service=llm)
    
    payload = {
        "context": "club_venue_conflict",
        "available_alternatives": [
            {
                "venue": "Auditorium",
                "start_time": "14:00",
                "end_time": "16:00",
                "capacity": 300
            }
        ]
    }
    
    resp = await bot.get_chat_response(user_query=json.dumps(payload))
    resp_dict = json.loads(resp)
    
    # Only the exactly matched alternative should survive
    assert len(resp_dict["recommendations"]) == 1
    assert resp_dict["recommendations"][0]["venue"] == "Auditorium"
    assert resp_dict["recommendations"][0]["start_time"] == "14:00"


# Test 6: LLM failure.
@pytest.mark.asyncio
async def test_club_venue_conflict_llm_failure():
    retrieval = MagicMock(spec=AIRetrievalService)
    retrieval.retrieve_context = AsyncMock(return_value=[])
    llm = MagicMock(spec=LLMService)
    
    llm.generate_response = AsyncMock(side_effect=Exception("Timeout"))
    bot = AIChatbot(retrieval_service=retrieval, llm_service=llm)
    
    payload = {
        "context": "club_venue_conflict",
        "available_alternatives": [{"venue": "X", "start_time": "1", "end_time": "2", "capacity": 10}]
    }
    
    resp = await bot.get_chat_response(user_query=json.dumps(payload))
    resp_dict = json.loads(resp)
    assert len(resp_dict["recommendations"]) == 0
    assert "temporarily unavailable" in resp_dict["summary"]


# Test 7: Malformed conflict payload.
@pytest.mark.asyncio
async def test_club_venue_conflict_malformed_payload():
    retrieval = MagicMock(spec=AIRetrievalService)
    retrieval.retrieve_context = AsyncMock(return_value=[])
    llm = MagicMock(spec=LLMService)
    llm.generate_response = AsyncMock(return_value=LLMResponse(success=True, content="Normal Response", tokens_used=10, latency_ms=100))
    
    bot = AIChatbot(retrieval_service=retrieval, llm_service=llm)
    
    # JSON but not dict
    resp = await bot.get_chat_response(user_query='["list", "instead", "of", "dict"]')
    assert resp == "Normal Response"
    
    # dict but bad JSON inside club_venue_conflict
    llm.generate_response = AsyncMock(return_value=LLMResponse(success=True, content="Bad JSON", tokens_used=10, latency_ms=100))
    payload = {
        "context": "club_venue_conflict",
        "available_alternatives": [{"venue": "X", "start_time": "1", "end_time": "2", "capacity": 10}]
    }
    resp = await bot.get_chat_response(user_query=json.dumps(payload))
    resp_dict = json.loads(resp)
    assert len(resp_dict["recommendations"]) == 0
    assert "temporarily unavailable" in resp_dict["summary"]


# Test 8: Empty alternatives.
@pytest.mark.asyncio
async def test_club_venue_conflict_empty_alternatives():
    retrieval = MagicMock(spec=AIRetrievalService)
    retrieval.retrieve_context = AsyncMock(return_value=[])
    llm = MagicMock(spec=LLMService)
    
    bot = AIChatbot(retrieval_service=retrieval, llm_service=llm)
    payload = {
        "context": "club_venue_conflict",
        "available_alternatives": []
    }
    resp = await bot.get_chat_response(user_query=json.dumps(payload))
    resp_dict = json.loads(resp)
    assert len(resp_dict["recommendations"]) == 0
    assert "No available alternatives" in resp_dict["summary"]


# Test 9: RAG does not override availability.
# Implicitly tested by the fact that valid_recommendations strictly filters against available_alternatives.
def test_build_messages_includes_context():
    msgs = build_club_venue_conflict_messages(
        event_title="A", event_description="B", requested_date="C",
        requested_start_time="D", requested_end_time="E", requested_venue="F",
        conflict_reason="G", available_alternatives=[], context_snippets=["Snippet123"]
    )
    assert "Snippet123" in msgs[0]["content"]
    assert "NEVER override availability" in msgs[0]["content"]

