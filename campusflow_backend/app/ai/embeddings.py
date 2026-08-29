from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("campusflow.ai.embeddings")


class EmbeddingService:
    """
    Service Layer responsible for generating vector representations of text.
    Supports pluggable providers: NVIDIA, Google Gemini, OpenAI, and local/mock fallbacks.
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        gemini_key: str | None = None,
        gemini_model: str | None = None,
        openai_key: str | None = None,
        openai_model: str | None = None,
        nvidia_key: str | None = None,
        nvidia_model: str | None = None,
    ) -> None:
        self.provider = (provider or os.environ.get("CAMPUSFLOW_EMBEDDING_PROVIDER", "mock")).lower().strip()
        
        self.gemini_key = gemini_key or os.environ.get("CAMPUSFLOW_GEMINI_API_KEY", "")
        self.gemini_model = gemini_model or os.environ.get("CAMPUSFLOW_GEMINI_EMBEDDING_MODEL", "text-embedding-004")

        self.openai_key = openai_key or os.environ.get("CAMPUSFLOW_OPENAI_API_KEY", "")
        self.openai_model = openai_model or os.environ.get("CAMPUSFLOW_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        self.nvidia_key = nvidia_key or os.environ.get("CAMPUSFLOW_NVIDIA_EMBEDDING_API_KEY") or os.environ.get("CAMPUSFLOW_NVIDIA_API_KEY", "")
        self.nvidia_model = nvidia_model or os.environ.get("CAMPUSFLOW_NVIDIA_EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b")

        # Visibility flag: True whenever the most recent get_embedding() call
        # silently fell back to the deterministic mock vector instead of a
        # real provider call, so callers/logs can't mistake a fallback vector
        # for a genuine embedding.
        self.last_call_used_fallback: bool = False

    async def get_embedding(self, *, text: str, input_type: str = "query") -> list[float]:
        self.last_call_used_fallback = self.provider not in ("gemini", "openai", "nvidia")
        if self.provider == "gemini":
            return await self._get_gemini_embedding(text=text)
        elif self.provider == "openai":
            return await self._get_openai_embedding(text=text)
        elif self.provider == "nvidia":
            return await self._get_nvidia_embedding(text=text, input_type=input_type)
        elif self.provider == "mock":
            return await self._get_mock_embedding(text=text)
        elif self.provider == "sentence-transformers":
            return await self._get_sentence_transformers_embedding(text=text)
        else:
            logger.warning(f"Unknown embedding provider: '{self.provider}'. Falling back to Mock.")
            return await self._get_mock_embedding(text=text)

    async def get_embeddings_batch(self, *, texts: list[str], input_type: str = "query") -> list[list[float]]:
        results = []
        for text in texts:
            emb = await self.get_embedding(text=text, input_type=input_type)
            results.append(emb)
        return results

    async def _get_nvidia_embedding(self, *, text: str, input_type: str) -> list[float]:
        if not self.nvidia_key:
            logger.warning("CAMPUSFLOW_NVIDIA_API_KEY is not set for embeddings.")

        url = "https://integrate.api.nvidia.com/v1/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.nvidia_key}"
        }
        payload = {
            "input": [text],
            "model": self.nvidia_model,
            "input_type": input_type,
            "truncate": "NONE"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            vec = data["data"][0]["embedding"]
            if len(vec) != 2048:
                # Never silently reshape/truncate/pad a wrong-dimension vector
                # (would corrupt the pgvector(2048) column with a mismatched
                # or misleading value) - raise so the existing except block
                # below routes this through the same MOCK FALLBACK ACTIVE
                # path as any other embedding-call failure.
                raise ValueError(
                    f"NVIDIA embedding API returned unexpected dimension "
                    f"{len(vec)} (expected 2048)")
            return vec
        except Exception as e:
            self.last_call_used_fallback = True
            logger.warning(
                f"MOCK FALLBACK ACTIVE: NVIDIA embedding API call failed ({str(e)}); "
                "returning a deterministic mock vector instead of a real embedding. "
                "NOTE: prior 2.0s timeout was almost certainly the historical root cause "
                "of NVIDIA embedding failures - now 30.0s."
            )
            return await self._get_mock_embedding(text=text)

    async def _get_gemini_embedding(self, *, text: str) -> list[float]:
        if not self.gemini_key:
            logger.warning("CAMPUSFLOW_GEMINI_API_KEY is not set for embeddings.")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:embedContent?key={self.gemini_key}"
        payload = {
            "model": f"models/{self.gemini_model}",
            "content": {
                "parts": [{"text": text}]
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            
            return data["embedding"]["values"]
        except Exception as e:
            self.last_call_used_fallback = True
            logger.warning(
                f"MOCK FALLBACK ACTIVE: Gemini embedding API call failed ({str(e)}); "
                "returning a deterministic mock vector instead of a real embedding."
            )
            return await self._get_mock_embedding(text=text)

    async def _get_openai_embedding(self, *, text: str) -> list[float]:
        if not self.openai_key:
            logger.warning("CAMPUSFLOW_OPENAI_API_KEY is not set for embeddings.")

        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_key}"
        }
        payload = {
            "input": text,
            "model": self.openai_model
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            return data["data"][0]["embedding"]
        except Exception as e:
            self.last_call_used_fallback = True
            logger.warning(
                f"MOCK FALLBACK ACTIVE: OpenAI embedding API call failed ({str(e)}); "
                "returning a deterministic mock vector instead of a real embedding."
            )
            return await self._get_mock_embedding(text=text)

    async def _get_sentence_transformers_embedding(self, *, text: str) -> list[float]:
        logger.info("Sentence Transformers local implementation not initialized. Using Mock fallback.")
        return await self._get_mock_embedding(text=text)

    async def _get_mock_embedding(self, *, text: str) -> list[float]:
        text_length = len(text)
        vector_len = 2048 # Nemotron 3 Embed 1B length
        
        base_val = (text_length % 100) / 100.0
        return [base_val + (i / 10000.0) for i in range(vector_len)]
