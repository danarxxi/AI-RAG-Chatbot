from abc import ABC, abstractmethod
from typing import List
from app.models.glossary import GlossaryTerm


class GlossaryRepository(ABC):
    """Abstract base class for glossary data access.

    This abstraction allows easy migration from Oracle to PostgreSQL
    by implementing a new repository class without changing service logic.
    """

    @abstractmethod
    def search_terms(self, keywords: List[str]) -> List[GlossaryTerm]:
        """Search glossary terms by keywords.

        Args:
            keywords: List of search terms extracted from user query

        Returns:
            List of matching GlossaryTerm objects
        """
        pass

    @abstractmethod
    def get_term_by_name(self, term_name: str) -> List[GlossaryTerm]:
        """Get glossary terms matching the exact or partial name.

        Args:
            term_name: Term name to search for

        Returns:
            List of matching GlossaryTerm objects
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass
