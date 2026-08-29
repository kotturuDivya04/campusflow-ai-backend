from __future__ import annotations

import logging
import os
import time

import httpx
from app.ai.schemas import LLMResponse

logger = logging.getLogger("campusflow.ai.llm_service")

class LLMService:
    """
    Service Layer wrapper for interacting with Large Language Model providers.
    Supports pluggable backends: OpenAI, Gemini, Ollama, and local Llama engines.
    
    Conforms to the existing Service Layer architecture by utilizing dependency-injected 
    client configuration patterns and keyword-only argument contracts.
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        openai_key: str | None = None,
        openai_model: str | None = None,
        openai_base_url: str | None = None,
        gemini_key: str | None = None,
        gemini_model: str | None = None,
        ollama_base_url: str | None = None,
        ollama_model: str | None = None,
        llama_base_url: str | None = None,
        llama_model: str | None = None,
    ) -> None:
        # Load settings following the config.py os.environ.get configuration pattern
        self.provider = (provider or os.environ.get("CAMPUSFLOW_LLM_PROVIDER", "mock")).lower().strip()

        # NVIDIA Configuration
        self.nvidia_key = os.environ.get("CAMPUSFLOW_NVIDIA_API_KEY", "")
        self.nvidia_model = os.environ.get("CAMPUSFLOW_NVIDIA_LLM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")

        # OpenAI Configuration
        self.openai_key = openai_key or os.environ.get("CAMPUSFLOW_OPENAI_API_KEY", "")
        self.openai_model = openai_model or os.environ.get("CAMPUSFLOW_OPENAI_MODEL", "gpt-4o")
        self.openai_base_url = openai_base_url or os.environ.get("CAMPUSFLOW_OPENAI_BASE_URL", "https://api.openai.com/v1")

        # Gemini Configuration
        self.gemini_key = gemini_key or os.environ.get("CAMPUSFLOW_GEMINI_API_KEY", "")
        self.gemini_model = gemini_model or os.environ.get("CAMPUSFLOW_GEMINI_MODEL", "gemini-1.5-flash")

        # Ollama Configuration
        self.ollama_base_url = ollama_base_url or os.environ.get("CAMPUSFLOW_OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = ollama_model or os.environ.get("CAMPUSFLOW_OLLAMA_MODEL", "llama3")

        # Llama Configuration (Generic OpenAI-compatible local endpoints)
        self.llama_base_url = llama_base_url or os.environ.get("CAMPUSFLOW_LLA_BASE_URL", "http://localhost:8000/v1")
        self.llama_model = llama_model or os.environ.get("CAMPUSFLOW_LLM_MODEL", "meta-llama/Llama-3-8B-Instruct")

    async def generate_response(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Routes the chat completion request to the active provider.
        Utilizes keyword-only arguments to match existing backend service conventions.

        Args:
            messages: List of role-content message dictionaries. E.g.
                      [{"role": "system", "content": "You are..."}, {"role": "user", "content": "..."}]
            temperature: LLM temperature parameter (default 0.7).
            max_tokens: Optional limit on completion tokens.
        """
        if self.provider == "openai":
            return await self._call_openai(messages=messages, temperature=temperature, max_tokens=max_tokens)
        elif self.provider == "nvidia":
            return await self._call_nvidia(messages=messages, temperature=temperature, max_tokens=max_tokens)
        elif self.provider == "gemini":
            return await self._call_gemini(messages=messages, temperature=temperature, max_tokens=max_tokens)
        elif self.provider == "ollama":
            return await self._call_ollama(messages=messages, temperature=temperature, max_tokens=max_tokens)
        elif self.provider == "llama":
            return await self._call_llama(messages=messages, temperature=temperature, max_tokens=max_tokens)
        elif self.provider == "mock":
            return await self._call_mock(messages=messages)
        else:
            error_msg = f"Unsupported LLM provider: {self.provider}"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                tokens_used=0,
                latency_ms=0,
                success=False,
                error_message=error_msg,
            )

    async def _call_openai_compatible(
        self,
        *,
        url: str,
        model: str,
        api_key: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResponse:
        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            latency = int((time.perf_counter() - start_time) * 1000)
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return LLMResponse(content=content, tokens_used=tokens, latency_ms=latency, success=True)
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"OpenAI-compatible call failed: {str(e)}")
            return LLMResponse(
                content="",
                tokens_used=0,
                latency_ms=latency,
                success=False,
                error_message=str(e),
            )

    async def _call_nvidia(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResponse:
        if not self.nvidia_key:
            logger.warning("CAMPUSFLOW_NVIDIA_API_KEY is not set.")
        return await self._call_openai_compatible(
            url="https://integrate.api.nvidia.com/v1/chat/completions",
            model=self.nvidia_model,
            api_key=self.nvidia_key,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _call_openai(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResponse:
        if not self.openai_key:
            logger.warning("CAMPUSFLOW_OPENAI_API_KEY is not set.")
        return await self._call_openai_compatible(
            url=f"{self.openai_base_url.rstrip('/')}/chat/completions",
            model=self.openai_model,
            api_key=self.openai_key,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _call_llama(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResponse:
        return await self._call_openai_compatible(
            url=f"{self.llama_base_url.rstrip('/')}/chat/completions",
            model=self.llama_model,
            api_key="",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _call_ollama(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResponse:
        url = f"{self.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            latency = int((time.perf_counter() - start_time) * 1000)
            content = data.get("message", {}).get("content", "")
            
            prompt_tokens = data.get("prompt_eval_count", 0)
            response_tokens = data.get("eval_count", 0)
            tokens = prompt_tokens + response_tokens

            return LLMResponse(content=content, tokens_used=tokens, latency_ms=latency, success=True)
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Ollama call failed: {str(e)}")
            return LLMResponse(
                content="",
                tokens_used=0,
                latency_ms=latency,
                success=False,
                error_message=str(e),
            )

    async def _call_gemini(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResponse:
        if not self.gemini_key:
            logger.warning("CAMPUSFLOW_GEMINI_API_KEY is not set.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"

        gemini_contents = []
        system_instruction_parts = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction_parts.append({"text": content})
            else:
                gemini_role = "model" if role == "assistant" else "user"
                gemini_contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })

        payload: dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": temperature
            }
        }
        if max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        if system_instruction_parts:
            payload["systemInstruction"] = {
                "parts": system_instruction_parts
            }

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            latency = int((time.perf_counter() - start_time) * 1000)
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("Gemini API response did not contain candidates.")
            
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(part.get("text", "") for part in parts)
            
            usage = data.get("usageMetadata", {})
            tokens = usage.get("totalTokenCount", 0)

            return LLMResponse(content=content, tokens_used=tokens, latency_ms=latency, success=True)
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Gemini call failed: {str(e)}")
            return LLMResponse(
                content="",
                tokens_used=0,
                latency_ms=latency,
                success=False,
                error_message=str(e),
            )

    async def _call_mock(
        self,
        *,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        """
        Mock response provider for testing/local development fallback.
        """
        start_time = time.perf_counter()
        user_query = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_query = m.get("content", "")
                break
        
        if "priority" in user_query.lower() or "assign" in user_query.lower():
            content = '{"priority_score": 85, "decision_reason": "Mocked AI Decision"}'
        else:
            content = f"[MOCK RESPONSE] You asked: {user_query[:100]}"
        latency = int((time.perf_counter() - start_time) * 1000)
        return LLMResponse(
            content=content,
            tokens_used=len(user_query.split()) + 10,
            latency_ms=latency,
            success=True,
        )

