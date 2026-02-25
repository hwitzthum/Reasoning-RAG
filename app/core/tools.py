"""Tool schemas and handlers for the reasoning orchestrator.

This module defines the 7 tools available to Claude Sonnet for document navigation
and the ToolHandler class that executes tool calls.
"""

import re
from typing import Any
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

READ_SECTION_PAGE_SIZE = 50
READ_SECTION_TEXT_CHAR_LIMIT = 2000
MAX_READ_PARAGRAPHS_ITEMS = 50
MAX_GREP_RESULTS = 20
GREP_CONTEXT_TEXT_CHAR_LIMIT = 500

# Tool schemas for Anthropic API (as per plan.md Section 7)
TOOLS = [
    {
        "name": "list_documents",
        "description": "List available documents with optional topic/language filtering",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Optional topic keyword to filter documents"
                },
                "language": {
                    "type": "string",
                    "enum": ["de", "fr", "it", "en"],
                    "description": "Filter by document language"
                }
            }
        }
    },
    {
        "name": "get_toc",
        "description": "Get the full Table of Contents tree for a document",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "The document ID"
                }
            },
            "required": ["doc_id"]
        }
    },
    {
        "name": "read_section",
        "description": "Read all paragraphs in a document section",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "The document ID"
                },
                "node_id": {
                    "type": "string",
                    "description": "Section node ID (e.g., 's001.1')"
                },
                "offset": {
                    "type": "integer",
                    "default": 0,
                    "description": "Paragraph offset for pagination (0-based)"
                }
            },
            "required": ["doc_id", "node_id"]
        }
    },
    {
        "name": "read_paragraphs",
        "description": "Read specific paragraphs by their IDs",
        "input_schema": {
            "type": "object",
            "properties": {
                "para_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 50,
                    "description": "List of paragraph IDs to read"
                }
            },
            "required": ["para_ids"]
        }
    },
    {
        "name": "grep_documents",
        "description": "Search for text patterns across documents. Use for cross-reference resolution and finding specific terms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": "Text or regex pattern to search"
                },
                "doc_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of doc_ids to search (null = all)"
                },
                "regex": {
                    "type": "boolean",
                    "default": False,
                    "description": "Interpret query_text as regex"
                },
                "context_paragraphs": {
                    "type": "integer",
                    "default": 1,
                    "description": "Include N surrounding paragraphs"
                },
                "max_results": {
                    "type": "integer",
                    "default": 10,
                    "maximum": 20,
                    "description": "Maximum number of results to return"
                }
            },
            "required": ["query_text"]
        }
    },
    {
        "name": "search_fallback",
        "description": "Embedding-based similarity search (Phase 2). Use when structural navigation fails.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": "Query text for semantic search"
                },
                "doc_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of doc_ids to search"
                },
                "top_k": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of results to return"
                }
            },
            "required": ["query_text"]
        }
    },
    {
        "name": "record_evidence",
        "description": "Record a paragraph as evidence for the current query",
        "input_schema": {
            "type": "object",
            "properties": {
                "para_id": {
                    "type": "string",
                    "description": "The paragraph ID to record as evidence"
                },
                "relevance_note": {
                    "type": "string",
                    "description": "Why this paragraph is relevant"
                }
            },
            "required": ["para_id", "relevance_note"]
        }
    }
]


class ToolHandler:
    """Execute tool calls from the orchestrator.

    This class implements all 7 tools that Claude Sonnet can use to navigate
    documents and build evidence. It maintains state for evidence tracking
    and visited section tracking.

    Attributes:
        db: Async database session
        doc_repo: Repository for document operations
        para_repo: Repository for paragraph operations
        evidence_log: List of evidence items recorded during reasoning
        visited_sections: Set of section keys already read (doc_id:node_id)
    """

    def __init__(self, db: AsyncSession):
        """Initialize tool handler with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db
        # Repositories will be imported lazily to avoid circular imports
        self.doc_repo = None
        self.para_repo = None
        self.embedding_search = None
        self.evidence_log: list[dict] = []
        self.visited_sections: set[str] = set()
        self._recorded_para_ids: set[str] = set()

    def _get_repositories(self) -> None:
        """Lazy-load repositories to avoid circular imports."""
        if self.doc_repo is None:
            from app.storage.repositories import DocumentRepository, ParagraphRepository
            self.doc_repo = DocumentRepository(self.db)
            self.para_repo = ParagraphRepository(self.db)

    async def execute(self, tool_name: str, tool_input: dict) -> Any:
        """Route tool call to appropriate handler.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Dictionary of tool parameters

        Returns:
            Tool-specific response data

        Raises:
            ValueError: If tool_name is not recognized
        """
        self._get_repositories()

        handlers = {
            "list_documents": self._list_documents,
            "get_toc": self._get_toc,
            "read_section": self._read_section,
            "read_paragraphs": self._read_paragraphs,
            "grep_documents": self._grep_documents,
            "search_fallback": self._search_fallback,
            "record_evidence": self._record_evidence,
        }

        handler = handlers.get(tool_name)
        if not handler:
            raise ValueError(f"Unknown tool: {tool_name}")

        result = await handler(**tool_input)

        # Safety-net evidence capture: record all read paragraph IDs even when
        # the model forgets to call record_evidence explicitly.
        if tool_name in {"read_section", "read_paragraphs"}:
            self._auto_record_from_tool_result(result)

        return result

    async def _list_documents(
        self,
        topic: str | None = None,
        language: str | None = None
    ) -> list[dict]:
        """List available documents with optional filtering.

        Args:
            topic: Optional keyword to filter by title/summary
            language: Optional language code filter (de, fr, it, en)

        Returns:
            List of document metadata dictionaries
        """
        docs = await self.doc_repo.list_documents(topic=topic, language=language)
        return [
            {
                "doc_id": d.doc_id,
                "title": d.title,
                "summary": d.summary,
                "language": d.language,
            }
            for d in docs
        ]

    async def _get_toc(self, doc_id: str) -> dict:
        """Get full ToC tree for a document.

        Args:
            doc_id: Document ID

        Returns:
            ToC JSON tree or error dict
        """
        doc = await self.doc_repo.get_by_id(doc_id)
        if not doc:
            return {"error": f"Document {doc_id} not found"}
        return doc.toc_json

    async def _read_section(self, doc_id: str, node_id: str, offset: int = 0) -> dict:
        """Read all paragraphs in a section.

        Marks section as visited to avoid re-reading.

        Args:
            doc_id: Document ID
            node_id: Section node ID (e.g., "s001.1")

        Returns:
            Dictionary with section info and paragraph list
        """
        section_key = f"{doc_id}:{node_id}"
        self.visited_sections.add(section_key)

        safe_offset = max(int(offset or 0), 0)
        paragraphs = await self.para_repo.get_by_section(
            doc_id,
            node_id,
            offset=safe_offset,
            limit=READ_SECTION_PAGE_SIZE + 1,
        )
        has_more = len(paragraphs) > READ_SECTION_PAGE_SIZE
        page_items = paragraphs[:READ_SECTION_PAGE_SIZE]

        return {
            "section": node_id,
            "offset": safe_offset,
            "limit": READ_SECTION_PAGE_SIZE,
            "has_more": has_more,
            "paragraphs": [
                {
                    "para_id": p.para_id,
                    "text": p.text[:READ_SECTION_TEXT_CHAR_LIMIT],
                    "page": p.page_number,
                }
                for p in page_items
            ]
        }

    async def _read_paragraphs(self, para_ids: list[str]) -> list[dict]:
        """Read specific paragraphs by ID.

        Used for targeted re-reading or cross-reference following.

        Args:
            para_ids: List of paragraph IDs

        Returns:
            List of paragraph dictionaries with full metadata
        """
        safe_para_ids = [para_id for para_id in para_ids if isinstance(para_id, str)][:MAX_READ_PARAGRAPHS_ITEMS]
        paragraphs = await self.para_repo.get_by_ids(safe_para_ids)
        return [
            {
                "para_id": p.para_id,
                "text": p.text,
                "page": p.page_number,
                "section_path": p.section_path,
            }
            for p in paragraphs
        ]

    async def _grep_documents(
        self,
        query_text: str,
        doc_ids: list[str] | None = None,
        regex: bool = False,
        context_paragraphs: int = 1,
        max_results: int = 10,
    ) -> list[dict] | dict:
        """Search for text patterns across documents.

        Critical for cross-reference resolution. Supports both plain text
        and regex searching with configurable context.

        Args:
            query_text: Search query or regex pattern
            doc_ids: Optional list of documents to search (None = all)
            regex: Whether to interpret query_text as regex
            context_paragraphs: Number of surrounding paragraphs to include
            max_results: Maximum results to return

        Returns:
            List of matching paragraphs with context, or error dict
        """
        try:
            safe_max_results = max(1, min(int(max_results or 10), MAX_GREP_RESULTS))
            results = await self.para_repo.search_text(
                query_text,
                doc_ids=doc_ids,
                regex=regex,
                limit=safe_max_results,
            )

            # Add context paragraphs if requested
            if context_paragraphs > 0:
                results = await self._add_context(results, context_paragraphs)

            return results
        except Exception as e:
            # Handle regex errors gracefully
            return {"error": f"Search failed: {str(e)}"}

    async def _add_context(
        self,
        results: list[dict],
        context_count: int
    ) -> list[dict]:
        """Add surrounding paragraphs to search results.

        Args:
            results: List of paragraph result dicts
            context_count: Number of paragraphs before/after to include

        Returns:
            Results with context_before and context_after fields added
        """
        safe_context_count = max(min(int(context_count or 0), 5), 0)
        if safe_context_count == 0 or not results:
            return results

        from app.storage.models import Paragraph

        enriched_results: list[dict] = []
        para_id_pattern = re.compile(r"^(?P<doc_id>[^:]+):(?P<section_id>[^:]+):p(?P<index>\d+)$")

        for item in results:
            para_id = item.get("para_id")
            if not isinstance(para_id, str):
                enriched_results.append(item)
                continue

            match = para_id_pattern.match(para_id)
            if match is None:
                enriched_results.append(item)
                continue

            doc_id = match.group("doc_id")
            section_id = match.group("section_id")
            para_index = int(match.group("index"))
            lower_bound = max(1, para_index - safe_context_count)
            upper_bound = para_index + safe_context_count

            stmt = (
                select(Paragraph)
                .where(
                    Paragraph.doc_id == doc_id,
                    Paragraph.section_id == section_id,
                    Paragraph.para_index >= lower_bound,
                    Paragraph.para_index <= upper_bound,
                )
                .order_by(Paragraph.para_index)
            )
            context_rows = (await self.db.execute(stmt)).scalars().all()

            context_before: list[dict] = []
            context_after: list[dict] = []
            for row in context_rows:
                entry = {
                    "para_id": row.para_id,
                    "text": row.text[:GREP_CONTEXT_TEXT_CHAR_LIMIT],
                    "page": row.page_number,
                }
                if row.para_index < para_index:
                    context_before.append(entry)
                elif row.para_index > para_index:
                    context_after.append(entry)

            enriched_item = dict(item)
            enriched_item["context_before"] = context_before[-safe_context_count:]
            enriched_item["context_after"] = context_after[:safe_context_count]
            enriched_results.append(enriched_item)

        return enriched_results

    async def _search_fallback(
        self,
        query_text: str,
        doc_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Embedding-based similarity search.

        Args:
            query_text: Query for semantic search
            doc_ids: Optional document scope
            top_k: Number of results
        """
        if self.embedding_search is None:
            from app.storage.embeddings import EmbeddingSearch

            self.embedding_search = EmbeddingSearch(self.db)
        return await self.embedding_search.search(query_text, doc_ids=doc_ids, top_k=top_k)

    async def _record_evidence(self, para_id: str, relevance_note: str) -> dict:
        """Record a paragraph as evidence.

        Builds up the evidence log throughout the reasoning loop.

        Args:
            para_id: Paragraph ID to record
            relevance_note: Why this paragraph is relevant

        Returns:
            Confirmation with current evidence count
        """
        evidence_item: dict[str, Any] = {
            "para_id": para_id,
            "relevance_note": relevance_note,
            "iteration": len(self.evidence_log) + 1,
        }

        self.evidence_log.append(evidence_item)
        self._recorded_para_ids.add(para_id)
        return {
            "recorded": True,
            "evidence_count": len(self.evidence_log)
        }

    def _sync_recorded_para_ids(self) -> None:
        """Backfill tracked para_ids from current evidence_log when needed."""
        for item in self.evidence_log:
            para_id = item.get("para_id")
            if isinstance(para_id, str) and para_id:
                self._recorded_para_ids.add(para_id)

    def _auto_record_from_tool_result(self, result: Any) -> None:
        """Add lightweight evidence entries after read tools return paragraphs."""
        para_ids: list[str] = []

        if isinstance(result, dict):
            paragraphs = result.get("paragraphs")
            if isinstance(paragraphs, list):
                for item in paragraphs:
                    if isinstance(item, dict):
                        para_id = item.get("para_id")
                        if isinstance(para_id, str) and para_id:
                            para_ids.append(para_id)
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    para_id = item.get("para_id")
                    if isinstance(para_id, str) and para_id:
                        para_ids.append(para_id)

        if not para_ids:
            return

        self._sync_recorded_para_ids()
        for para_id in para_ids:
            if para_id in self._recorded_para_ids:
                continue
            self.evidence_log.append(
                {
                    "para_id": para_id,
                    "relevance_note": "Auto-recorded from read tool output",
                    "iteration": len(self.evidence_log) + 1,
                    "auto_recorded": True,
                }
            )
            self._recorded_para_ids.add(para_id)

    async def enrich_evidence_log(self) -> None:
        """Batch-enrich recorded evidence entries with paragraph/document metadata."""
        para_ids = [
            item["para_id"]
            for item in self.evidence_log
            if isinstance(item.get("para_id"), str)
            and item.get("para_id")
            and item.get("doc_id") is None
        ]
        if not para_ids:
            return

        unique_para_ids = list(dict.fromkeys(para_ids))
        from app.storage.models import Document, Paragraph, Section

        stmt = (
            select(
                Paragraph.para_id,
                Paragraph.doc_id,
                Paragraph.section_id,
                Paragraph.section_path,
                Paragraph.page_number,
                Document.title.label("doc_title"),
                Section.title.label("section_title"),
            )
            .select_from(Paragraph)
            .join(Document, Paragraph.doc_id == Document.doc_id, isouter=True)
            .join(
                Section,
                and_(
                    Section.doc_id == Paragraph.doc_id,
                    Section.section_id == Paragraph.section_id,
                ),
                isouter=True,
            )
            .where(Paragraph.para_id.in_(unique_para_ids))
        )
        rows = (await self.db.execute(stmt)).all()

        metadata_by_para_id = {
            row.para_id: {
                "doc_id": row.doc_id,
                "doc_title": row.doc_title,
                "section_id": row.section_id,
                "section_title": row.section_title,
                "section_path": row.section_path,
                "page_number": row.page_number,
            }
            for row in rows
        }

        for evidence_item in self.evidence_log:
            para_id = evidence_item.get("para_id")
            if not isinstance(para_id, str):
                continue
            metadata = metadata_by_para_id.get(para_id)
            if metadata:
                evidence_item.update(
                    {key: value for key, value in metadata.items() if value is not None}
                )
