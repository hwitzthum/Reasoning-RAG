"""Dependency injection for FastAPI routes.

This module provides dependency functions for injecting services and repositories
into route handlers. Re-exports database session dependency and provides factory
functions for repositories and cache management.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database import get_db
from app.storage.cache import CacheManager
from app.storage.repositories import DocumentRepository, ParagraphRepository

# Re-export database session dependency for convenience
__all__ = ["get_db", "get_document_repository", "get_paragraph_repository", "get_cache_manager"]


def get_document_repository(
    db: AsyncSession = Depends(get_db),
) -> DocumentRepository:
    """
    Dependency for injecting DocumentRepository.

    Creates a DocumentRepository instance with the current database session.

    Args:
        db: Database session from get_db dependency

    Returns:
        DocumentRepository: Repository instance for document operations

    Usage:
        @router.get("/documents")
        async def list_docs(
            doc_repo: DocumentRepository = Depends(get_document_repository)
        ):
            return await doc_repo.list_documents()
    """
    return DocumentRepository(db)


def get_paragraph_repository(
    db: AsyncSession = Depends(get_db),
) -> ParagraphRepository:
    """
    Dependency for injecting ParagraphRepository.

    Creates a ParagraphRepository instance with the current database session.

    Args:
        db: Database session from get_db dependency

    Returns:
        ParagraphRepository: Repository instance for paragraph operations

    Usage:
        @router.get("/paragraphs")
        async def search_paragraphs(
            para_repo: ParagraphRepository = Depends(get_paragraph_repository)
        ):
            return await para_repo.search_text(query="example")
    """
    return ParagraphRepository(db)


def get_cache_manager(
    db: AsyncSession = Depends(get_db),
) -> CacheManager:
    """Dependency for injecting CacheManager."""
    return CacheManager(db)
