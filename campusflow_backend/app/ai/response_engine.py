from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("campusflow.ai.response_engine")


class AIResponseEngine:
    """
    Service Layer responsible for parsing, sanitizing, and validating LLM responses.
    Ensures that raw text outputs from generative models conform to expected format layouts.
    
    Conforms to existing backend conventions by utilizing keyword-only argument contracts.
    """

    def clean_text(self, *, text: str) -> str:
        """
        Cleans markdown wrappers, stripping code fences and leading/trailing whitespace.
        
        Args:
            text: Raw generative response string.
        """
        cleaned = text.strip()

        # Remove markdown code fences (e.g. ```json ... ``` or ```text ... ```)
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) > 0 and lines[0].startswith("```"):
                lines = lines[1:]
            if len(lines) > 0 and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # Normalize carriage returns and vertical spacing
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned

    def parse_json(self, *, text: str) -> dict[str, Any] | None:
        """
        Sanitizes text and parses it as a JSON object.
        Returns None if parsing fails.

        Args:
            text: Raw response string.
        """
        cleaned = self.clean_text(text=text)
        try:
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {str(e)}. Content: '{text}'")
            return None

    def validate_keys(
        self,
        *,
        data: dict[str, Any],
        required_keys: list[str],
    ) -> bool:
        """
        Validates that all required fields/keys are present in a parsed dictionary.

        Args:
            data: Parsed dictionary payload.
            required_keys: List of expected string keys.
        """
        return all(key in data for key in required_keys)

    def standardize_error(
        self,
        *,
        message: str,
        code: str = "AI_PROCESSING_ERROR",
    ) -> dict[str, Any]:
        """
        Builds a consistent error envelope dictionary.

        Args:
            message: Plaintext error explanation.
            code: Standardized error code.
        """
        return {
            "success": False,
            "error": {
                "code": code,
                "message": message
            }
        }

    def standardize_success(self, *, data: Any) -> dict[str, Any]:
        """
        Builds a consistent success envelope dictionary.

        Args:
            data: Payload dictionary, list, or text.
        """
        return {
            "success": True,
            "data": data
        }
