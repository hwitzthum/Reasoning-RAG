"""Cache management for L1-L5 cache layers.

This module implements the unified cache manager that handles:
- L1: Ingestion cache (file hash deduplication)
- L2: ToC corpus cache (in-memory combined ToCs)
- L3: Embedding cache (Phase 2)
- L4: Query result cache
- L5: Reasoning trace storage (forever retention)
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Text as SqlText
from sqlalchemy import cast, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.storage.models import Document, QueryCache, ReasoningTrace

_toc_corpus_cache: dict[str, Any] | None = None
_toc_corpus_cache_version = 0
logger = logging.getLogger(__name__)


class CacheManager:
    """
    Unified cache manager for all cache layers.

    Manages five distinct cache layers:
    - L1: Ingestion cache (filesystem-based, keyed by file_hash)
    - L2: ToC corpus cache (in-memory, invalidated on any doc change)
    - L4: Query result cache (SQL, invalidated when cited docs change)
    - L5: Reasoning trace cache (SQL, never invalidated - audit trail)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize cache manager with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session

    # ==================== L1: Ingestion Cache ====================

    async def get_ingestion_cache(self, file_hash: str) -> Document | None:
        """
        Check if a file has already been processed (L1 cache).

        Uses file hash to detect duplicate uploads and avoid re-processing.

        Args:
            file_hash: SHA-256 hash of the file content

        Returns:
            Document if already ingested, None otherwise
        """
        result = await self.session.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    # ==================== L2: ToC Corpus Cache ====================

    async def get_toc_corpus(self) -> dict[str, Any]:
        """
        Get combined ToC for all documents (L2 cache).

        This is loaded into memory at startup and used to pre-populate
        the system prompt with document structure. Invalidated when any
        document is added, updated, or deleted.

        Returns:
            Dictionary mapping doc_id to toc_json for all documents
        """
        global _toc_corpus_cache
        if _toc_corpus_cache is None:
            result = await self.session.execute(select(Document))
            documents = result.scalars().all()
            _toc_corpus_cache = {doc.doc_id: doc.toc_json for doc in documents}

        return _toc_corpus_cache

    def invalidate_toc_corpus(self) -> None:
        """
        Invalidate the in-memory ToC corpus cache (L2).

        Called when any document is added, updated, or deleted.
        Forces reload on next get_toc_corpus() call.
        """
        global _toc_corpus_cache, _toc_corpus_cache_version
        _toc_corpus_cache = None
        _toc_corpus_cache_version += 1

    # ==================== L4: Query Result Cache ====================

    async def get_query_result(
        self, query: str, doc_scope: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Check for cached query result (L4 cache).

        Args:
            query: The query text
            doc_scope: Optional list of doc_ids that limit query scope

        Returns:
            Cached result dict if found, None otherwise
            Dict contains: answer, confidence, citations, evidence_log, etc.
        """
        query_hash = self._compute_query_hash(query, doc_scope)

        result = await self.session.execute(
            select(QueryCache).where(QueryCache.query_hash == query_hash)
        )
        cached = result.scalar_one_or_none()

        if cached:
            if self._is_cache_entry_expired(cached.created_at):
                await self.session.execute(
                    delete(QueryCache).where(QueryCache.query_hash == cached.query_hash)
                )
                await self.session.commit()
                return None

            return {
                "answer": cached.answer,
                "confidence": cached.confidence,
                "citations": cached.citations,
                "evidence_log": cached.evidence_log,
                "sections_explored": cached.sections_explored,
                "iterations": cached.iterations,
                "cache_hit": True,
            }

        return None

    async def cache_query_result(
        self,
        query: str,
        doc_scope: list[str] | None,
        result: dict[str, Any],
    ) -> None:
        """
        Store query result in cache (L4).

        Args:
            query: The query text
            doc_scope: Optional list of doc_ids that limit query scope
            result: Query result dict with answer, confidence, citations, etc.
        """
        query_hash = self._compute_query_hash(query, doc_scope)

        cache_entry = QueryCache(
            query_hash=query_hash,
            query_text=query,
            doc_scope=doc_scope,
            answer=result["answer"],
            confidence=result.get("confidence"),
            citations=result.get("citations", []),
            cited_doc_ids=self._extract_cited_doc_ids(result, doc_scope=doc_scope),
            evidence_log=result.get("evidence_log"),
            sections_explored=result.get("sections_explored"),
            iterations=result.get("iterations"),
        )

        # Upsert: delete existing if present, then insert
        await self.session.execute(delete(QueryCache).where(QueryCache.query_hash == query_hash))
        self.session.add(cache_entry)
        await self.session.commit()

    async def invalidate_for_document(self, doc_id: str) -> None:
        """
        Invalidate all caches related to a specific document.

        Called when a document is deleted or updated. Invalidates:
        - L2: ToC corpus (entire cache)
        - L4: All query results that cite this document

        Args:
            doc_id: Document identifier to invalidate caches for
        """
        # L2: Invalidate ToC corpus
        self.invalidate_toc_corpus()

        # L4: Delete cached results that reference this document ID in either
        # cited_doc_ids or explicit doc_scope using SQL-side filtering.
        escaped_doc_id = doc_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        doc_id_pattern = f'%"{escaped_doc_id}"%'
        para_doc_pattern = f"%{escaped_doc_id}:%"
        await self.session.execute(
            delete(QueryCache).where(
                or_(
                    cast(QueryCache.cited_doc_ids, SqlText).like(doc_id_pattern, escape="\\"),
                    cast(QueryCache.doc_scope, SqlText).like(doc_id_pattern, escape="\\"),
                    cast(QueryCache.citations, SqlText).like(doc_id_pattern, escape="\\"),
                    cast(QueryCache.citations, SqlText).like(para_doc_pattern, escape="\\"),
                    cast(QueryCache.evidence_log, SqlText).like(para_doc_pattern, escape="\\"),
                )
            )
        )

        await self.session.commit()

    # ==================== L5: Reasoning Trace Storage ====================

    async def store_reasoning_trace(
        self,
        query_id: str,
        query_text: str,
        trace: list[dict[str, Any]],
        answer: str | None,
        latency_ms: int,
    ) -> None:
        """
        Store full reasoning trace for audit and debugging (L5).

        This cache has no TTL - traces are retained forever for compliance
        and debugging purposes.

        Args:
            query_id: Unique query identifier (UUID)
            query_text: The original query text
            trace: Full tool call sequence with inputs and outputs
            answer: Final answer generated (optional on failures)
            latency_ms: Total query latency in milliseconds
        """
        # Count tool call iterations
        iterations = sum(1 for t in trace if t.get("type") == "tool_call")

        trace_entry = ReasoningTrace(
            query_id=query_id,
            query_text=query_text,
            trace_json=trace,
            answer=answer,
            latency_ms=latency_ms,
            iterations=iterations,
        )
        try:
            self.session.add(trace_entry)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to persist reasoning trace for query %s", query_id)

    async def get_reasoning_trace(self, query_id: str) -> ReasoningTrace | None:
        """
        Retrieve a reasoning trace by query ID (L5).

        Args:
            query_id: Unique query identifier

        Returns:
            ReasoningTrace if found, None otherwise
        """
        result = await self.session.execute(
            select(ReasoningTrace).where(ReasoningTrace.query_id == query_id)
        )
        return result.scalar_one_or_none()

    def _is_cache_entry_expired(self, created_at: datetime | None) -> bool:
        """Return True when an L4 cache entry has exceeded configured TTL."""
        if created_at is None:
            return False

        ttl_seconds = settings.query_cache_ttl_seconds
        if ttl_seconds <= 0:
            return False

        if created_at.tzinfo is None:
            created_at_utc = created_at.replace(tzinfo=UTC)
        else:
            created_at_utc = created_at.astimezone(UTC)
        age_seconds = (datetime.now(UTC) - created_at_utc).total_seconds()
        return age_seconds > ttl_seconds

    # ==================== Private Helper Methods ====================

    def _compute_query_hash(self, query: str, doc_scope: list[str] | None) -> str:
        """
        Compute SHA-256 hash for query cache key.

        Combines query text and document scope to create unique cache key.

        Args:
            query: The query text
            doc_scope: Optional list of doc_ids limiting scope

        Returns:
            64-character hex SHA-256 hash
        """
        # Normalize query (lowercase, strip whitespace)
        normalized_query = query.lower().strip()

        # Sort doc_scope for consistent hashing
        if doc_scope:
            sorted_scope = sorted(doc_scope)
            scope_str = json.dumps(sorted_scope)
        else:
            scope_str = ""

        # Combine and hash
        cache_key = f"{normalized_query}|{scope_str}"
        return hashlib.sha256(cache_key.encode("utf-8")).hexdigest()

    def _extract_cited_doc_ids(
        self,
        result: dict[str, Any],
        doc_scope: list[str] | None = None,
    ) -> list[str]:
        """Extract document IDs referenced by citations/evidence/doc_scope."""
        doc_ids: set[str] = set()

        citations = result.get("citations")
        if isinstance(citations, list):
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                citation_doc_id = citation.get("doc_id")
                if isinstance(citation_doc_id, str) and citation_doc_id:
                    doc_ids.add(citation_doc_id)
                for para_key in ("verified_para_id", "para_id"):
                    para_id = citation.get(para_key)
                    if isinstance(para_id, str) and ":" in para_id:
                        doc_ids.add(para_id.split(":", 1)[0])

        evidence_log = result.get("evidence_log")
        if isinstance(evidence_log, list):
            for evidence_item in evidence_log:
                if not isinstance(evidence_item, dict):
                    continue
                evidence_doc_id = evidence_item.get("doc_id")
                if isinstance(evidence_doc_id, str) and evidence_doc_id:
                    doc_ids.add(evidence_doc_id)
                para_id = evidence_item.get("para_id")
                if isinstance(para_id, str) and ":" in para_id:
                    doc_ids.add(para_id.split(":", 1)[0])

        if isinstance(doc_scope, list):
            for scope_doc_id in doc_scope:
                if isinstance(scope_doc_id, str) and scope_doc_id:
                    doc_ids.add(scope_doc_id)

        return sorted(doc_ids)
