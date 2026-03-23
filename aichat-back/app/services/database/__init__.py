from .base import GlossaryRepository
from .postgresql_repository import PostgreSQLGlossaryRepository

__all__ = ["GlossaryRepository", "PostgreSQLGlossaryRepository"]
