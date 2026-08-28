from abc import ABC, abstractmethod
from typing import Any

class BaseParser(ABC):
    """Abstract base class defining the interface for all timetable file parsers."""
    
    @abstractmethod
    def parse(self, file_path: str) -> list[dict[str, Any]]:
        """Parses the input file and returns a list of raw row records (key-value pairs).
        
        Args:
            file_path: The absolute path to the target file.
            
        Returns:
            A list of dictionary records where keys are the raw column headers.
        """
        pass
