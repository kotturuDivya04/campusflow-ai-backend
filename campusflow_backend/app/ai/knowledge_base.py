from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from app.ai.schemas import KnowledgeBaseEntry

logger = logging.getLogger("campusflow.ai.knowledge_base")

class AIKnowledgeBaseService:
    """
    Service Layer responsible for managing campus FAQ and knowledge base documents.
    Provides CRUD operations and context retrieval preparation for RAG integrations.
    
    Conforms to existing backend service layer patterns by utilizing dependency injection 
    and enforcing keyword-only argument contracts.
    """

    def __init__(self, *, db_session: Any = None) -> None:
        # db_session will be a SQLAlchemy Session instance in future DB implementation steps
        self._db = db_session
        from app.ai.repository import AIKnowledgeBaseRepository
        self._repo = AIKnowledgeBaseRepository(session=self._db) if self._db else None

    async def process_upload(
        self,
        *,
        file_content: bytes,
        filename: str,
        content_type: str,
        embedding_service: Any,
    ) -> int:
        """
        Extracts text from uploaded documents, splits into chunks, generates embeddings,
        and saves each chunk to the knowledge base.
        Returns the number of chunks processed.
        """
        import io
        import docx
        import pypdf
        
        text = ""
        
        if "pdf" in content_type.lower() or filename.lower().endswith(".pdf"):
            reader = pypdf.PdfReader(io.BytesIO(file_content))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif "wordprocessingml.document" in content_type.lower() or filename.lower().endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif "text" in content_type.lower() or filename.lower().endswith((".txt", ".md")):
            text = file_content.decode("utf-8", errors="ignore")
        else:
            raise ValueError(f"Unsupported file format: {content_type}")
            
        if not text.strip():
            logger.warning(f"No text could be extracted from {filename}")
            return 0
            
        chunks = []
        chunk_size = 800
        overlap = 100
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(text[start:end])
            if end == text_len:
                break
            start += chunk_size - overlap
            
        if not self._repo:
            raise RuntimeError("Database session not initialized.")
            
        count = 0
        for i, chunk_text in enumerate(chunks):
            if not chunk_text.strip():
                continue
                
            embedding = await embedding_service.get_embedding(text=chunk_text, input_type="passage")
            
            title = f"{filename}_chunk_{i+1}"
            question = f"Document excerpt from {filename}"
            answer = chunk_text.strip()
            
            self._repo.create(
                title=title,
                question=question,
                answer=answer,
                category="document_upload",
                tags="document,ingestion",
                embedding_vector=embedding
            )
            count += 1
            
        return count

    async def create_entry(
        self,
        *,
        title: str,
        question: str,
        answer: str,
        category: str,
        tags: list[str] | None = None,
    ) -> KnowledgeBaseEntry:
        """
        Creates a new FAQ/knowledge record.
        """
        logger.info(f"Creating knowledge entry: '{title}' in category '{category}'")
        
        if not self._repo:
            raise RuntimeError("Database session not initialized.")
            
        tags_str = ",".join(tags) if tags else ""
        record = self._repo.create(
            title=title,
            question=question,
            answer=answer,
            category=category,
            tags=tags_str
        )
        
        return KnowledgeBaseEntry(
            id=record.id,
            title=record.title,
            question=record.question,
            answer=record.answer,
            category=record.category,
            tags=record.tags.split(",") if record.tags else [],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def get_entry(self, *, entry_id: int) -> KnowledgeBaseEntry | None:
        """
        Retrieves a single knowledge entry by ID.
        """
        logger.info(f"Retrieving knowledge entry ID: {entry_id}")
        
        if not self._repo:
            raise RuntimeError("Database session not initialized.")
            
        record = self._repo.get_by_id(entry_id)
        if not record:
            return None
            
        return KnowledgeBaseEntry(
            id=record.id,
            title=record.title,
            question=record.question,
            answer=record.answer,
            category=record.category,
            tags=record.tags.split(",") if record.tags else [],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def update_entry(
        self,
        *,
        entry_id: int,
        title: str | None = None,
        question: str | None = None,
        answer: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> KnowledgeBaseEntry:
        """
        Updates fields of an existing knowledge entry.
        """
        logger.info(f"Updating knowledge entry ID: {entry_id}")
        
        if not self._repo:
            raise RuntimeError("Database session not initialized.")
            
        tags_str = ",".join(tags) if tags is not None else None
        
        record = self._repo.update(
            entry_id=entry_id,
            title=title,
            question=question,
            answer=answer,
            category=category,
            tags=tags_str
        )
        if not record:
            raise ValueError(f"Entry with ID {entry_id} not found.")
            
        return KnowledgeBaseEntry(
            id=record.id,
            title=record.title,
            question=record.question,
            answer=record.answer,
            category=record.category,
            tags=record.tags.split(",") if record.tags else [],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def delete_entry(self, *, entry_id: int) -> bool:
        """
        Deletes a knowledge entry by ID.
        """
        logger.info(f"Deleting knowledge entry ID: {entry_id}")
        
        if not self._repo:
            raise RuntimeError("Database session not initialized.")
            
        return self._repo.delete(entry_id)

    async def list_entries(
        self,
        *,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeBaseEntry]:
        """
        Lists knowledge base entries with optional category filter.
        """
        logger.info(f"Listing knowledge entries (category={category}, limit={limit}, offset={offset})")
        
        if not self._repo:
            raise RuntimeError("Database session not initialized.")
            
        records = self._repo.list_entries(category=category, limit=limit, offset=offset)
        return [
            KnowledgeBaseEntry(
                id=record.id,
                title=record.title,
                question=record.question,
                answer=record.answer,
                category=record.category,
                tags=record.tags.split(",") if record.tags else [],
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            for record in records
        ]

    async def retrieve_matching_context(
        self,
        *,
        query: str,
        limit: int = 3,
    ) -> list[str]:
        """
        Fallback path only reached when AIRetrievalService could not use the
        real pgvector similarity search. This must NEVER return fabricated
        "context" text - a caller cannot tell fake context from a genuine
        retrieved chunk, and injecting made-up policy text into an LLM prompt
        as if it were real KB content is exactly the "fake RAG shipped as
        real" failure mode this module must avoid. Return nothing instead,
        loudly, so the chatbot answers from general knowledge without
        pretending it consulted CampusFlow's KB.
        """
        logger.warning(
            f"AIKnowledgeBaseService.retrieve_matching_context() called without a "
            f"real repository (db_session not wired) for query: '{query}'. "
            f"Returning NO context rather than fabricated placeholder text."
        )
        return []
