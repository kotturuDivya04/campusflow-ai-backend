from __future__ import annotations

import logging
from typing import Any

from app.ai.embeddings import EmbeddingService
from app.ai.knowledge_base import AIKnowledgeBaseService

logger = logging.getLogger("campusflow.ai.retrieval")


class AIRetrievalService:
    """
    Service Layer responsible for Retrieval-Augmented Generation (RAG) context matching.
    Coordinates vector embeddings generation and query similarity search over the knowledge base.
    
    Conforms to existing backend service layer patterns by utilizing dependency injection 
    and enforcing keyword-only argument contracts.
    """

    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        knowledge_base_service: AIKnowledgeBaseService,
    ) -> None:
        self._embeddings = embedding_service
        self._kb = knowledge_base_service

    async def retrieve_context(self, *, query: str, limit: int = 3) -> list[str]:
        """
        Retrieves the most semantically relevant knowledge base snippets matching the query.
        Returns an ordered list of context strings ready to be injected into prompts.

        Args:
            query: User's natural language question.
            limit: Maximum number of context snippets to return.
        """
        # Step 1: Generate a vector embedding for the input query text
        query_vector = await self._embeddings.get_embedding(text=query)
        logger.info(f"Generated query vector embedding of dimensions: {len(query_vector)}")

        # If the real provider call failed and get_embedding() silently
        # returned the deterministic MOCK vector instead, a pgvector
        # similarity search against it would return whichever KB rows
        # happen to be nearest to that meaningless vector - i.e. genuinely
        # irrelevant entries that would still look like real, relevant
        # [CONTEXT] snippets to the LLM and the user. Never run that search;
        # return honestly empty instead, exactly like the no-repo fallback.
        if getattr(self._embeddings, "last_call_used_fallback", False):
            logger.warning(
                "Query embedding used the MOCK FALLBACK vector (real embedding "
                "provider call failed) - skipping similarity search and "
                "returning NO context rather than risk irrelevant matches."
            )
            return []
        
        # Step 2: Query database records for cosine similarity matching.
        # A real repo genuinely returning zero matches (empty/irrelevant KB)
        # must be returned AS-IS - honestly empty - and must NOT fall through
        # to Step 3, which is a "no repository wired at all" fallback whose
        # own log message ("db_session not wired") would be actively
        # misleading here (the repo WAS wired and DID run a real pgvector
        # search; it just found nothing). Re-routing a genuine empty result
        # through that path also risks a second, redundant lookup and
        # confuses "no DB" with "DB says no match" in the logs/audit trail.
        if hasattr(self._kb, '_repo') and self._kb._repo:
            records = self._kb._repo.search_similar_entries(query_vector=query_vector, limit=limit)
            snippets = [f"[CONTEXT] {r.title}: {r.answer}" for r in records]
            logger.info(
                f"Retrieved {len(snippets)} relevant snippets from the knowledge base "
                f"repository (real pgvector search; empty means no relevant match, "
                f"NOT a fallback)."
            )
            return snippets

        # Step 3: only reached when there is genuinely no repository/DB
        # session wired at all - never for a real, merely-empty search.
        snippets = await self._kb.retrieve_matching_context(query=query, limit=limit)
        
        logger.info(f"Retrieved {len(snippets)} relevant snippets from the knowledge base service fallback.")
        return snippets
