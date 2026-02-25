"""Checkpoint-based recovery for resumable document ingestion."""

from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.storage.models import IngestionCheckpoint


class CheckpointManager:
    """
    Manage ingestion checkpoints for resumable document processing.

    Allows ingestion pipeline to save state at each stage and resume from
    the last successful checkpoint on failure.

    Valid stages: parsing, structure, paragraphs, annotation, cross_refs, indexing
    """

    VALID_STAGES = {
        "parsing",
        "structure",
        "paragraphs",
        "annotation",
        "cross_refs",
        "indexing",
    }

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize checkpoint manager.

        Args:
            db: Async database session for checkpoint operations
        """
        self.db = db

    async def get(self, doc_id: str) -> Optional[IngestionCheckpoint]:
        """
        Retrieve checkpoint for a document.

        Args:
            doc_id: Document identifier

        Returns:
            IngestionCheckpoint if exists, None otherwise
        """
        result = await self.db.execute(
            select(IngestionCheckpoint).where(IngestionCheckpoint.doc_id == doc_id)
        )
        return result.scalar_one_or_none()

    async def save(
        self,
        doc_id: str,
        stage: str,
        stage_data: dict[str, Any],
    ) -> None:
        """
        Save or update checkpoint for a document stage.

        Args:
            doc_id: Document identifier
            stage: Current stage name (must be in VALID_STAGES)
            stage_data: Stage-specific state data to persist

        Raises:
            ValueError: If stage is not valid

        Note:
            Uses upsert behavior - creates new checkpoint or updates existing one.
        """
        if stage not in self.VALID_STAGES:
            raise ValueError(
                f"Invalid stage '{stage}'. Must be one of: {', '.join(self.VALID_STAGES)}"
            )

        # Check if checkpoint exists
        existing = await self.get(doc_id)

        if existing:
            # Update existing checkpoint
            existing.stage = stage
            existing.stage_data = stage_data
            existing.error_message = None  # Clear any previous error
        else:
            # Create new checkpoint
            checkpoint = IngestionCheckpoint(
                doc_id=doc_id,
                stage=stage,
                stage_data=stage_data,
            )
            self.db.add(checkpoint)

        await self.db.commit()

    async def delete(self, doc_id: str) -> None:
        """
        Delete checkpoint for a document.

        Args:
            doc_id: Document identifier

        Note:
            Called after successful ingestion completion to clean up checkpoint.
        """
        await self.db.execute(
            delete(IngestionCheckpoint).where(IngestionCheckpoint.doc_id == doc_id)
        )
        await self.db.commit()

    async def update_error(self, doc_id: str, error_msg: str) -> None:
        """
        Update checkpoint with error message on failure.

        Args:
            doc_id: Document identifier
            error_msg: Error message describing the failure

        Note:
            Preserves stage and stage_data for potential manual recovery.
        """
        checkpoint = await self.get(doc_id)

        if checkpoint:
            checkpoint.error_message = error_msg
            await self.db.commit()
