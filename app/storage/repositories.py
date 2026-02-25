"""Repository layer for database operations.

This module provides repository classes that encapsulate database access
patterns for Documents, Paragraphs, and other entities.
"""

import re
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import CrossReference, Document, Paragraph, Section


class DocumentRepository:
    """
    Repository for Document CRUD operations.

    Handles all database interactions for Document entities including
    creation, retrieval, listing with filters, and deletion.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session

    async def create(
        self,
        doc_id: str,
        title: str,
        file_type: str,
        language: str,
        total_pages: int,
        file_hash: str,
        toc_json: dict[str, Any],
        summary: str | None = None,
        original_filename: str | None = None,
    ) -> Document:
        """
        Create a new document record.

        Args:
            doc_id: Unique document identifier (12-char UUID)
            title: Document title
            file_type: File extension (pdf, docx, pptx)
            language: Document language (de, fr, it, en)
            total_pages: Number of pages in document
            file_hash: SHA-256 hash of original file for deduplication
            toc_json: Full table of contents JSON structure
            summary: Optional document-level summary
            original_filename: Original uploaded filename

        Returns:
            Created Document instance
        """
        document = Document(
            doc_id=doc_id,
            title=title,
            file_type=file_type,
            language=language,
            total_pages=total_pages,
            file_hash=file_hash,
            toc_json=toc_json,
            summary=summary,
            original_filename=original_filename,
        )
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def get_by_id(self, doc_id: str) -> Document | None:
        """
        Retrieve a document by its ID.

        Args:
            doc_id: Document identifier

        Returns:
            Document if found, None otherwise
        """
        result = await self.session.execute(select(Document).where(Document.doc_id == doc_id))
        return result.scalar_one_or_none()

    async def get_by_file_hash(self, file_hash: str) -> Document | None:
        """
        Find document by file hash (for deduplication).

        Args:
            file_hash: SHA-256 hash of file content

        Returns:
            Document if found, None otherwise
        """
        result = await self.session.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self, topic: str | None = None, language: str | None = None
    ) -> list[Document]:
        """
        List all documents with optional filtering.

        Args:
            topic: Optional topic keyword to search in title and summary
            language: Optional language filter (de, fr, it, en)

        Returns:
            List of matching documents
        """
        query = select(Document)

        if language:
            query = query.where(Document.language == language)

        if topic:
            # Case-insensitive search in title and summary
            topic_filter = f"%{topic}%"
            query = query.where(
                (Document.title.ilike(topic_filter)) | (Document.summary.ilike(topic_filter))
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete(self, doc_id: str) -> bool:
        """
        Delete a document and all related entities (cascade).

        Args:
            doc_id: Document identifier to delete

        Returns:
            True if document was deleted, False if not found
        """
        result = await self.session.execute(delete(Document).where(Document.doc_id == doc_id))
        await self.session.commit()
        return result.rowcount > 0


class ParagraphRepository:
    """
    Repository for Paragraph CRUD operations.

    Handles paragraph retrieval, bulk creation, and text search operations
    including support for regex patterns.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session

    async def create_bulk(self, paragraphs: list[Paragraph]) -> int:
        """
        Create multiple paragraphs in a single transaction.

        Args:
            paragraphs: List of Paragraph instances to insert

        Returns:
            Number of paragraphs created
        """
        self.session.add_all(paragraphs)
        await self.session.commit()
        return len(paragraphs)

    async def get_by_ids(self, para_ids: list[str]) -> list[Paragraph]:
        """
        Retrieve multiple paragraphs by their IDs.

        Args:
            para_ids: List of paragraph IDs to retrieve

        Returns:
            List of Paragraph instances (may be fewer than requested if some not found)
        """
        result = await self.session.execute(select(Paragraph).where(Paragraph.para_id.in_(para_ids)))
        return list(result.scalars().all())

    async def get_by_section(
        self,
        doc_id: str,
        section_id: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Paragraph]:
        """
        Retrieve all paragraphs in a specific section.

        Args:
            doc_id: Document identifier
            section_id: Section identifier (e.g., "s001.1")

        Returns:
            List of paragraphs in the section, ordered by para_index
        """
        stmt = (
            select(Paragraph)
            .where(Paragraph.doc_id == doc_id, Paragraph.section_id == section_id)
            .order_by(Paragraph.para_index)
            .offset(max(offset, 0))
        )
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_text(
        self,
        query: str,
        doc_ids: list[str] | None = None,
        regex: bool = False,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search for text patterns across paragraphs.

        Supports both simple text search (LIKE) and regex pattern matching.
        Used by the grep_documents tool for cross-reference resolution and text search.

        Args:
            query: Text or regex pattern to search for
            doc_ids: Optional list of document IDs to limit search scope
            regex: If True, interpret query as regex pattern
            limit: Maximum number of results to return

        Returns:
            List of dicts with keys: para_id, text, page_number, section_path, doc_id

        Raises:
            ValueError: If regex pattern is invalid
        """
        # Build base query with doc_id filter applied at SQL level
        stmt = select(Paragraph)

        if doc_ids:
            stmt = stmt.where(Paragraph.doc_id.in_(doc_ids))

        matches: list[dict[str, Any]] = []

        if regex:
            # Regex cannot be pushed into SQLite without a registered REGEXP function.
            # Cap the pre-execution scan so at most 500 rows are loaded before Python filtering.
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")

            result = await self.session.execute(stmt.limit(min(limit * 20, 500)))
            for para in result.scalars():
                if pattern.search(para.text):
                    matches.append(
                        {
                            "para_id": para.para_id,
                            "text": para.text,
                            "page_number": para.page_number,
                            "section_path": para.section_path,
                            "doc_id": para.doc_id,
                        }
                    )
                    if len(matches) >= limit:
                        break
        else:
            # Push case-insensitive substring search into SQL using ILIKE / LIKE.
            stmt = stmt.where(Paragraph.text.ilike(f"%{query}%")).limit(limit)
            result = await self.session.execute(stmt)
            for para in result.scalars():
                matches.append(
                    {
                        "para_id": para.para_id,
                        "text": para.text,
                        "page_number": para.page_number,
                        "section_path": para.section_path,
                        "doc_id": para.doc_id,
                    }
                )

        return matches


class CrossReferenceRepository:
    """Repository for cross-reference indexing and lookup."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_bulk(self, references: list[CrossReference]) -> int:
        """Insert a batch of cross-reference records."""
        if not references:
            return 0
        self.session.add_all(references)
        await self.session.commit()
        return len(references)

    async def get_unresolved(self, doc_id: str | None = None) -> list[CrossReference]:
        """Return unresolved cross-references, optionally scoped to one document."""
        stmt = select(CrossReference).where(CrossReference.resolved.is_(False))

        if doc_id:
            escaped = doc_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(CrossReference.source_para_id.like(f"{escaped}:%", escape="\\"))

        result = await self.session.execute(stmt.order_by(CrossReference.created_at.desc()))
        return list(result.scalars().all())

    async def list_for_document(self, doc_id: str) -> list[CrossReference]:
        """Return all cross-references emitted by a document."""
        escaped = doc_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = (
            select(CrossReference)
            .where(CrossReference.source_para_id.like(f"{escaped}:%", escape="\\"))
            .order_by(CrossReference.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
