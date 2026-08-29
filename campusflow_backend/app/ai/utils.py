import logging

logger = logging.getLogger("campusflow.ai.utils")

def format_prompt_text(text: str) -> str:
    """Utility to safely format strings going into a prompt."""
    return text.strip()
