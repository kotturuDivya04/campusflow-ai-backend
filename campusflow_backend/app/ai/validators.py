from typing import Any

def validate_chat_input(message: str) -> bool:
    """Validate chat message length and content."""
    if not message or len(message.strip()) == 0:
        return False
    return True
