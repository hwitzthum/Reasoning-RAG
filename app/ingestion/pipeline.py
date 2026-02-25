"""Document ingestion pipeline coordinator.

This module orchestrates the full document ingestion workflow with
checkpoint-based recovery and atomic transaction handling.
"""

import hashlib
import asyncio
import re
from pathlib import Path
from typing import Callable, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.ingestion.docling_parser import DoclingParser, validate_file
from app.ingestion.structure import MarkdownStructureAnalyzer, ParagraphExtractor
from app.ingestion.annotator import HaikuAnnotator
from app.ingestion.cross_references import CrossReferenceExtractor
from app.ingestion.checkpoints import CheckpointManager
from app.storage.repositories import DocumentRepository
from app.storage.models import Document, Section, Paragraph, CrossReference
from app.storage.embeddings import EmbeddingSearch


# Ingestion stage constants (aligned with CheckpointManager.VALID_STAGES)
class IngestionStage:
    """Constants for ingestion pipeline stages."""
    PARSED = "parsing"
    STRUCTURED = "structure"
    PARAGRAPHS_EXTRACTED = "paragraphs"
    ANNOTATED = "annotation"
    XREFS_EXTRACTED = "cross_refs"
    SAVED = "indexing"


class PipelineError(Exception):
    """Raised when pipeline execution fails."""
    pass


class IngestionPipeline:
    """Coordinates full document ingestion workflow.

    Orchestrates parsing, structure analysis, annotation, and storage
    with checkpoint-based recovery and progress reporting.

    Attributes:
        db: Async database session
        parser: Docling document parser
        structure_analyzer: Markdown structure analyzer
        paragraph_extractor: Paragraph extraction handler
        annotator: Haiku-based section annotator
        xref_extractor: Cross-reference extraction handler
        checkpoint_manager: Checkpoint recovery manager
        doc_repo: Document repository for database operations
    """

    def __init__(self, db: AsyncSession):
        """Initialize pipeline with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db
        self.parser = DoclingParser()
        self.structure_analyzer = MarkdownStructureAnalyzer()
        self.paragraph_extractor = ParagraphExtractor()
        self.annotator = HaikuAnnotator()
        self.xref_extractor = CrossReferenceExtractor()
        self.checkpoint_manager = CheckpointManager(db)
        self.doc_repo = DocumentRepository(db)
        self.embedding_search = EmbeddingSearch(db)

    async def ingest_document(
        self,
        file_path: Path,
        doc_id: str | None = None,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> str:
        """Ingest a document with full pipeline processing.

        This is the main entry point for document ingestion. It handles:
        - File validation
        - Checkpoint-based recovery
        - Full parsing and annotation workflow
        - Atomic database transactions
        - Progress reporting

        Args:
            file_path: Path to document file (PDF, DOCX, or PPTX)
            doc_id: Optional explicit document identifier override
            progress_callback: Optional callback for progress updates
                               Signature: (stage_name: str, progress: float) -> None

        Returns:
            str: The document ID of the ingested document

        Raises:
            PipelineError: If any stage of ingestion fails
            ValueError: If file is invalid or unsupported
        """
        # Validate file
        if not validate_file(file_path):
            raise ValueError(f"Invalid or unsupported file: {file_path}")

        # Derive document ID from explicit override or filename.
        doc_id = (doc_id or "").strip() or file_path.stem

        # Calculate file hash for deduplication
        file_hash = self._calculate_file_hash(file_path)

        # Check for existing checkpoint
        checkpoint = await self.checkpoint_manager.get(doc_id)

        if checkpoint:
            # Resume from checkpoint
            return await self._resume_from_checkpoint(
                file_path,
                doc_id,
                file_hash,
                checkpoint,
                progress_callback,
            )
        else:
            # Start fresh ingestion
            return await self._run_full_pipeline(
                file_path,
                doc_id,
                file_hash,
                progress_callback,
            )

    async def _run_full_pipeline(
        self,
        file_path: Path,
        doc_id: str,
        file_hash: str,
        progress_callback: Callable[[str, float], None] | None,
    ) -> str:
        """Run the complete ingestion pipeline from scratch.

        Args:
            file_path: Path to document file
            doc_id: Document identifier
            file_hash: SHA-256 hash of file content
            progress_callback: Optional progress callback

        Returns:
            str: Document ID

        Raises:
            PipelineError: If any stage fails
        """
        try:
            # Stage 1: Parse document
            self._report_progress(progress_callback, "Parsing document", 0.1)

            # Special case: if file is .md (for testing), read directly
            if file_path.suffix.lower() == ".md":
                import aiofiles
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    markdown = await f.read()
                metadata = {
                    "title": file_path.stem,
                    "page_count": 1,  # Markdown doesn't have pages
                    "file_type": "md",
                    "original_filename": file_path.name,
                }
            else:
                # Normal case: use Docling parser
                markdown, metadata = await self.parser.parse(file_path)
                metadata.setdefault("original_filename", file_path.name)

            await self.checkpoint_manager.save(
                doc_id,
                IngestionStage.PARSED,
                {"markdown": markdown, "metadata": metadata, "file_hash": file_hash},
            )

            # Stage 2: Analyze structure
            self._report_progress(progress_callback, "Analyzing structure", 0.3)
            sections = self.structure_analyzer.analyze(markdown)

            # Convert sections to dicts for JSON serialization
            from dataclasses import asdict
            sections_dicts = [asdict(s) for s in sections]

            await self.checkpoint_manager.save(
                doc_id,
                IngestionStage.STRUCTURED,
                {"sections": sections_dicts},
            )

            # Stage 3: Extract paragraphs
            self._report_progress(progress_callback, "Extracting paragraphs", 0.4)
            paragraphs_data = self.paragraph_extractor.extract(doc_id, sections)

            # Convert paragraphs to dicts for JSON serialization
            paragraphs_dicts = [asdict(p) for p in paragraphs_data]

            await self.checkpoint_manager.save(
                doc_id,
                IngestionStage.PARAGRAPHS_EXTRACTED,
                {"paragraphs": paragraphs_dicts},
            )

            # Stage 4: Annotate sections with Haiku
            self._report_progress(progress_callback, "Annotating sections", 0.5)

            # Build simple ToC tree from dataclass sections
            toc_tree = self._build_simple_toc(sections, paragraphs_data)

            # Convert paragraphs list to dict grouped by section_id
            paragraphs_by_section: dict[str, list[dict]] = {}
            for para in paragraphs_data:
                section_id = para.section_id
                if section_id not in paragraphs_by_section:
                    paragraphs_by_section[section_id] = []
                paragraphs_by_section[section_id].append(asdict(para))

            annotated_toc = await self._annotate_toc_tree(
                toc_tree,
                paragraphs_by_section,
                file_hash,
                progress_callback,
            )

            await self.checkpoint_manager.save(
                doc_id,
                IngestionStage.ANNOTATED,
                {"annotated_toc": annotated_toc},
            )

            # Stage 5: Extract cross-references
            self._report_progress(progress_callback, "Extracting cross-references", 0.7)
            xrefs = self._extract_cross_references(paragraphs_by_section)

            await self.checkpoint_manager.save(
                doc_id,
                IngestionStage.XREFS_EXTRACTED,
                {"xrefs": xrefs},
            )

            # Stage 6: Save to database (atomic transaction)
            self._report_progress(progress_callback, "Saving to database", 0.8)
            doc_id = await self._save_to_database(
                doc_id,
                file_path,
                file_hash,
                metadata,
                annotated_toc,
                paragraphs_by_section,
                xrefs,
            )

            await self.checkpoint_manager.save(
                doc_id,
                IngestionStage.SAVED,
                {"doc_id": doc_id},
            )

            # Stage 7: Cleanup checkpoint
            self._report_progress(progress_callback, "Finalizing", 0.9)
            await self.checkpoint_manager.delete(doc_id)

            self._report_progress(progress_callback, "Complete", 1.0)
            return doc_id

        except Exception as e:
            # Checkpoint is preserved for recovery
            raise PipelineError(f"Pipeline failed: {str(e)}") from e

    async def _resume_from_checkpoint(
        self,
        file_path: Path,
        doc_id: str,
        file_hash: str,
        checkpoint: Any,  # IngestionCheckpoint ORM object
        progress_callback: Callable[[str, float], None] | None,
    ) -> str:
        """Resume ingestion from a saved checkpoint.

        Args:
            file_path: Path to document file
            doc_id: Document identifier
            file_hash: SHA-256 hash of file content
            checkpoint: IngestionCheckpoint ORM object
            progress_callback: Optional progress callback

        Returns:
            str: Document ID

        Raises:
            PipelineError: If resume fails
        """
        stage = checkpoint.stage
        data = checkpoint.stage_data

        # Verify file integrity: if the PARSED checkpoint stored a hash and the current
        # file has a different hash, the source file changed — restart from scratch.
        if stage == IngestionStage.PARSED:
            stored_hash = data.get("file_hash")
            if stored_hash and stored_hash != file_hash:
                logger.warning(
                    "File changed since checkpoint for %s — restarting ingestion", doc_id
                )
                await self.checkpoint_manager.delete(doc_id)
                return await self._run_full_pipeline(file_path, doc_id, file_hash, progress_callback)

        self._report_progress(
            progress_callback,
            f"Resuming from {stage}",
            0.0,
        )

        try:
            # Resume based on last completed stage
            if stage == IngestionStage.PARSED:
                # Re-run from structure analysis
                markdown = data["markdown"]
                metadata = data["metadata"]

                toc_tree = self.structure_analyzer.build_toc_tree(markdown)
                await self.checkpoint_manager.save(
                doc_id,
                    IngestionStage.STRUCTURED,
                    {"toc_tree": toc_tree},
                )

                paragraphs_data = self.paragraph_extractor.extract_all(
                    markdown,
                    toc_tree,
                )
                await self.checkpoint_manager.save(
                doc_id,
                    IngestionStage.PARAGRAPHS_EXTRACTED,
                    {"paragraphs": paragraphs_data},
                )

                annotated_toc = await self._annotate_toc_tree(
                    toc_tree,
                    paragraphs_data,
                    file_hash,
                    progress_callback,
                )
                await self.checkpoint_manager.save(
                doc_id,
                    IngestionStage.ANNOTATED,
                    {"annotated_toc": annotated_toc},
                )

                xrefs = self._extract_cross_references(paragraphs_data)
                await self.checkpoint_manager.save(
                doc_id,
                    IngestionStage.XREFS_EXTRACTED,
                    {"xrefs": xrefs},
                )

                doc_id = await self._save_to_database(
                    doc_id,
                    file_path,
                    file_hash,
                    metadata,
                    annotated_toc,
                    paragraphs_data,
                    xrefs,
                )

            elif stage == IngestionStage.STRUCTURED:
                # Re-run from paragraph extraction
                toc_tree = data["toc_tree"]

                # Need to re-parse for markdown content
                markdown, metadata = await self.parser.parse(file_path)

                paragraphs_data = self.paragraph_extractor.extract_all(
                    markdown,
                    toc_tree,
                )
                await self.checkpoint_manager.save(
                doc_id,
                    IngestionStage.PARAGRAPHS_EXTRACTED,
                    {"paragraphs": paragraphs_data},
                )

                annotated_toc = await self._annotate_toc_tree(
                    toc_tree,
                    paragraphs_data,
                    file_hash,
                    progress_callback,
                )
                await self.checkpoint_manager.save(
                doc_id,
                    IngestionStage.ANNOTATED,
                    {"annotated_toc": annotated_toc},
                )

                xrefs = self._extract_cross_references(paragraphs_data)
                await self.checkpoint_manager.save(
                doc_id,
                    IngestionStage.XREFS_EXTRACTED,
                    {"xrefs": xrefs},
                )

                doc_id = await self._save_to_database(
                    doc_id,
                    file_path,
                    file_hash,
                    metadata,
                    annotated_toc,
                    paragraphs_data,
                    xrefs,
                )

            elif stage == IngestionStage.PARAGRAPHS_EXTRACTED:
                # Re-run from annotation
                stored_paragraphs = data["paragraphs"]
                paragraphs_by_section: dict[str, list[dict]] = {}
                for para in stored_paragraphs:
                    section_id = para["section_id"]
                    if section_id not in paragraphs_by_section:
                        paragraphs_by_section[section_id] = []
                    paragraphs_by_section[section_id].append(para)

                # Need to reconstruct ToC structure.
                if file_path.suffix.lower() == ".md":
                    markdown = file_path.read_text(encoding="utf-8")
                    metadata = {
                        "title": file_path.stem,
                        "page_count": 1,
                        "file_type": "md",
                    }
                else:
                    markdown, metadata = await self.parser.parse(file_path)

                sections = self.structure_analyzer.analyze(markdown)
                # _build_simple_toc expects objects with section_id attributes.
                from types import SimpleNamespace
                paragraph_refs = [
                    SimpleNamespace(section_id=p["section_id"]) for p in stored_paragraphs
                ]
                toc_tree = self._build_simple_toc(sections, paragraph_refs)

                annotated_toc = await self._annotate_toc_tree(
                    toc_tree,
                    paragraphs_by_section,
                    file_hash,
                    progress_callback,
                )
                await self.checkpoint_manager.save(
                    doc_id,
                    IngestionStage.ANNOTATED,
                    {"annotated_toc": annotated_toc},
                )

                xrefs = self._extract_cross_references(paragraphs_by_section)
                await self.checkpoint_manager.save(
                    doc_id,
                    IngestionStage.XREFS_EXTRACTED,
                    {"xrefs": xrefs},
                )

                doc_id = await self._save_to_database(
                    doc_id,
                    file_path,
                    file_hash,
                    metadata,
                    annotated_toc,
                    paragraphs_by_section,
                    xrefs,
                )

            elif stage == IngestionStage.ANNOTATED:
                # Re-run from cross-reference extraction
                annotated_toc = data["annotated_toc"]

                # Need paragraph data
                markdown, metadata = await self.parser.parse(file_path)
                sections = self.structure_analyzer.analyze(markdown)
                paragraphs_data = self.paragraph_extractor.extract(doc_id, sections)

                xrefs = self._extract_cross_references(paragraphs_data)
                await self.checkpoint_manager.save(
                doc_id,
                    IngestionStage.XREFS_EXTRACTED,
                    {"xrefs": xrefs},
                )

                doc_id = await self._save_to_database(
                    doc_id,
                    file_path,
                    file_hash,
                    metadata,
                    annotated_toc,
                    paragraphs_data,
                    xrefs,
                )

            elif stage == IngestionStage.XREFS_EXTRACTED:
                # Re-run database save only
                # Need all data
                markdown, metadata = await self.parser.parse(file_path)
                annotated_toc = data.get("annotated_toc")
                xrefs = data["xrefs"]

                paragraphs_data = self.paragraph_extractor.extract_all(
                    markdown,
                    annotated_toc or self.structure_analyzer.build_toc_tree(markdown),
                )

                doc_id = await self._save_to_database(
                    doc_id,
                    file_path,
                    file_hash,
                    metadata,
                    annotated_toc,
                    paragraphs_data,
                    xrefs,
                )

            elif stage == IngestionStage.SAVED:
                # Already complete - return doc_id
                doc_id = data["doc_id"]

            else:
                raise PipelineError(f"Unknown checkpoint stage: {stage}")

            # Clear checkpoint
            await self.checkpoint_manager.delete(doc_id)
            self._report_progress(progress_callback, "Complete", 1.0)

            return doc_id

        except Exception as e:
            raise PipelineError(f"Resume failed: {str(e)}") from e

    async def _annotate_toc_tree(
        self,
        toc_tree: list[dict],
        paragraphs_data: dict[str, list[dict]],
        file_hash: str,
        progress_callback: Callable[[str, float], None] | None,
    ) -> list[dict]:
        """Annotate ToC tree with Haiku summaries and metadata.

        Args:
            toc_tree: ToC tree structure
            paragraphs_data: Extracted paragraphs by section
            file_hash: Document file hash
            progress_callback: Optional progress callback

        Returns:
            Annotated ToC tree with summaries and language
        """
        total_sections = self._count_sections(toc_tree)
        sections_processed = 0
        semaphore = asyncio.Semaphore(10)
        progress_lock = asyncio.Lock()

        def flatten_nodes(nodes: list[dict]) -> list[dict]:
            collected: list[dict] = []
            for node in nodes:
                collected.append(node)
                sub_nodes = node.get("sub_nodes")
                if isinstance(sub_nodes, list) and sub_nodes:
                    collected.extend(flatten_nodes(sub_nodes))
            return collected

        all_nodes = flatten_nodes(toc_tree)

        async def annotate_node(node: dict) -> dict:
            nonlocal sections_processed

            # Get paragraph text for this section
            section_id = node["node_id"]
            paras = paragraphs_data.get(section_id, [])
            text_content = "\n".join(p["text"] for p in paras)

            if text_content:
                # Bound outbound annotation concurrency to avoid provider throttling.
                async with semaphore:
                    annotation = await self.annotator.annotate_section(
                        node["title"],
                        text_content,
                    )
                node["summary"] = annotation["summary"]
                node["language"] = annotation["language"]

            async with progress_lock:
                sections_processed += 1
                if progress_callback and total_sections > 0:
                    progress = 0.5 + (0.2 * sections_processed / total_sections)
                    self._report_progress(
                        progress_callback,
                        f"Annotating sections ({sections_processed}/{total_sections})",
                        progress,
                    )

            return node

        await asyncio.gather(*(annotate_node(node) for node in all_nodes))
        return toc_tree

    def _extract_cross_references(
        self,
        paragraphs_data: dict[str, list[dict]],
    ) -> list[dict]:
        """Extract cross-references from all paragraphs.

        Args:
            paragraphs_data: Extracted paragraphs by section

        Returns:
            List of cross-reference dictionaries
        """
        all_xrefs = []

        for section_id, paras in paragraphs_data.items():
            for para in paras:
                xrefs = self.xref_extractor.extract(para["text"])

                for xref in xrefs:
                    all_xrefs.append({
                        "source_para_id": para["para_id"],
                        "reference_text": xref["source_text"],
                        "target_hint": xref["target_hint"],
                    })

        return all_xrefs

    async def _save_to_database(
        self,
        doc_id: str,
        file_path: Path,
        file_hash: str,
        metadata: dict,
        toc_tree: list[dict],
        paragraphs_data: dict[str, list[dict]],
        xrefs: list[dict],
    ) -> str:
        """Save all ingestion data to database atomically.

        Args:
            doc_id: Stable document identifier
            file_path: Original file path
            file_hash: SHA-256 hash of file
            metadata: Document metadata
            toc_tree: Annotated ToC tree
            paragraphs_data: Extracted paragraphs
            xrefs: Cross-references

        Returns:
            str: Document ID

        Raises:
            PipelineError: If database save fails
        """
        try:
            # Check if document already exists (re-ingestion case)
            from sqlalchemy import select, delete as sql_delete
            existing_doc_result = await self.db.execute(
                select(Document).where(Document.doc_id == doc_id)
            )
            existing_doc = existing_doc_result.scalar_one_or_none()

            if existing_doc:
                # Delete existing document and all related data manually
                # (CASCADE should handle this, but being explicit)
                escaped_doc_id = doc_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                await self.db.execute(
                    sql_delete(CrossReference).where(
                        CrossReference.source_para_id.like(f"{escaped_doc_id}:%", escape="\\")
                    )
                )
                await self.db.execute(
                    sql_delete(Paragraph).where(Paragraph.doc_id == doc_id)
                )
                await self.db.execute(
                    sql_delete(Section).where(Section.doc_id == doc_id)
                )
                await self.db.execute(
                    sql_delete(Document).where(Document.doc_id == doc_id)
                )
                await self.db.flush()  # Flush but don't commit yet

            doc = Document(
                doc_id=doc_id,
                title=metadata.get("title", doc_id),
                file_type=metadata.get("file_type", file_path.suffix.lstrip(".").lower()),
                file_hash=file_hash,
                total_pages=metadata.get("page_count", 1),
                toc_json=toc_tree,
                language=self._detect_primary_language(toc_tree),
                summary=self._generate_doc_summary(toc_tree),
                original_filename=metadata.get("original_filename"),
            )

            # Add document to session
            self.db.add(doc)

            # Create sections and paragraphs
            section_objects = []
            paragraph_objects = []

            for node in toc_tree:
                self._create_sections_recursive(
                    node,
                    doc_id,
                    paragraphs_data,
                    section_objects,
                    paragraph_objects,
                )

            # Add all sections and paragraphs
            self.db.add_all(section_objects)
            self.db.add_all(paragraph_objects)

            # Create cross-references
            node_lookup = self._build_toc_node_lookup(toc_tree)
            xref_objects = []
            for xref in xrefs:
                source_para_id = xref["source_para_id"]
                target_hint = xref.get("target_hint")
                target_doc_id, target_node_id, resolved = self._resolve_cross_reference_target(
                    target_hint,
                    doc_id,
                    node_lookup,
                )

                # Add outgoing xref details to the source section in ToC JSON.
                source_section_id = self._extract_section_id_from_para_id(source_para_id)
                source_node = node_lookup.get(source_section_id)
                if source_node is not None:
                    source_refs = source_node.setdefault("cross_references", [])
                    source_refs.append(
                        {
                            "reference_text": xref["reference_text"],
                            "target_hint": target_hint,
                            "resolved": resolved,
                            "target_doc_id": target_doc_id,
                            "target_node_id": target_node_id,
                        }
                    )

                xref_objects.append(
                    CrossReference(
                        source_para_id=source_para_id,
                        source_text=xref["reference_text"],
                        target_doc_id=target_doc_id,
                        target_node_id=target_node_id,
                        resolved=resolved,
                    )
                )
            self.db.add_all(xref_objects)

            # Commit transaction
            await self.db.commit()
            # Invalidate shared L2 ToC cache after any ingestion/re-ingestion write.
            from app.storage.cache import CacheManager
            CacheManager(self.db).invalidate_toc_corpus()

            # Phase 2: best-effort embedding indexing after the main transaction commits.
            # Running this after commit ensures DB is consistent even if indexing fails.
            try:
                await self._update_embedding_index(paragraphs_data)
            except Exception as e:
                logger.warning("Embedding index update failed (non-fatal): %s", e)

            return doc_id

        except SQLAlchemyError as e:
            await self.db.rollback()
            raise PipelineError(f"Database save failed: {str(e)}") from e

    def _create_sections_recursive(
        self,
        node: dict,
        doc_id: str,
        paragraphs_data: dict[str, list[dict]],
        section_objects: list[Section],
        paragraph_objects: list[Paragraph],
        parent_id: str | None = None,
        section_path: list[str] | None = None,
    ) -> None:
        """Recursively create section and paragraph objects.

        Args:
            node: ToC tree node
            doc_id: Document ID
            paragraphs_data: Extracted paragraphs
            section_objects: List to append section objects to
            paragraph_objects: List to append paragraph objects to
            parent_id: Parent section ID (None for root sections)
            section_path: Hierarchical title path up to the current node
        """
        section_id = node["node_id"]
        current_title = str(node.get("title") or section_id)
        current_path = [*(section_path or []), current_title]

        # Create section
        section = Section(
            section_id=section_id,
            doc_id=doc_id,
            parent_section_id=parent_id,
            title=node["title"],
            heading_level=node.get("level", 1),
            summary=node.get("summary"),
            page_start=node.get("page_range", [None, None])[0],
            page_end=node.get("page_range", [None, None])[1],
            section_path=current_path,
        )
        section_objects.append(section)

        # Create paragraphs for this section
        paras = paragraphs_data.get(section_id, [])
        for para in paras:
            paragraph = Paragraph(
                para_id=para["para_id"],
                section_id=section_id,
                doc_id=doc_id,
                text=para["text"],
                para_index=para["para_index"],
                page_number=para.get("page"),
                markdown_source=para.get("markdown_source"),
                section_path=current_path,
            )
            paragraph_objects.append(paragraph)

        # Recursively process sub-nodes
        for sub_node in node.get("sub_nodes", []):
            self._create_sections_recursive(
                sub_node,
                doc_id,
                paragraphs_data,
                section_objects,
                paragraph_objects,
                parent_id=section_id,
                section_path=current_path,
            )

    def _detect_primary_language(self, toc_tree: list[dict]) -> str:
        """Detect primary document language from ToC annotations.

        Args:
            toc_tree: Annotated ToC tree

        Returns:
            str: ISO language code (e.g., 'de', 'en', 'fr')
        """
        languages = []

        def collect_languages(node: dict) -> None:
            if node.get("language"):
                languages.append(node["language"])
            for sub in node.get("sub_nodes", []):
                collect_languages(sub)

        for node in toc_tree:
            collect_languages(node)

        # Return most common language
        if languages:
            return max(set(languages), key=languages.count)
        else:
            return "unknown"

    def _generate_doc_summary(self, toc_tree: list[dict]) -> str:
        """Generate document-level summary from section summaries.

        Args:
            toc_tree: Annotated ToC tree

        Returns:
            str: Document summary
        """
        summaries = []

        def collect_summaries(node: dict, depth: int = 0) -> None:
            if depth == 0 and node.get("summary"):
                summaries.append(node["summary"])
            for sub in node.get("sub_nodes", []):
                collect_summaries(sub, depth + 1)

        for node in toc_tree:
            collect_summaries(node)

        if summaries:
            return " ".join(summaries[:3])  # First 3 top-level summaries
        else:
            return "No summary available."

    def _count_sections(self, toc_tree: list[dict]) -> int:
        """Count total sections in ToC tree.

        Args:
            toc_tree: ToC tree structure

        Returns:
            int: Total section count
        """
        count = 0

        def count_recursive(node: dict) -> None:
            nonlocal count
            count += 1
            for sub in node.get("sub_nodes", []):
                count_recursive(sub)

        for node in toc_tree:
            count_recursive(node)

        return count

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file content.

        Args:
            file_path: Path to file

        Returns:
            str: Hex-encoded SHA-256 hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _build_simple_toc(
        self,
        sections: list,
        paragraphs: list
    ) -> list[dict]:
        """Build simple hierarchical ToC from dataclass sections.

        Args:
            sections: List of Section dataclass objects
            paragraphs: List of Paragraph dataclass objects

        Returns:
            list: Hierarchical ToC tree structure
        """
        if not sections:
            return []

        # Count paragraphs per section
        para_counts = {}
        for para in paragraphs:
            section_id = para.section_id
            para_counts[section_id] = para_counts.get(section_id, 0) + 1

        # Build section map
        section_map = {s.section_id: s for s in sections}

        # Build hierarchical structure
        root_nodes = []
        nodes_by_id = {}

        for section in sections:
            node = {
                "node_id": section.section_id,
                "title": section.title,
                "level": section.heading_level,
                "paragraph_count": para_counts.get(section.section_id, 0),
                "cross_references": [],
                "sub_nodes": []
            }

            if section.page_start is not None and section.page_end is not None:
                node["page_range"] = [section.page_start, section.page_end]

            nodes_by_id[section.section_id] = node

            if section.parent_id is None:
                root_nodes.append(node)
            elif section.parent_id in nodes_by_id:
                nodes_by_id[section.parent_id]["sub_nodes"].append(node)

        return root_nodes

    async def _update_embedding_index(self, paragraphs_data: dict[str, list[dict]]) -> int:
        """Best-effort embedding index update for Phase 2 semantic fallback."""
        flattened: list[dict] = []
        for paras in paragraphs_data.values():
            flattened.extend(paras)

        if not flattened:
            return 0

        try:
            return await self.embedding_search.index_paragraphs(flattened)
        except Exception:
            # Embedding generation is optional and must never break ingestion.
            return 0

    def _build_toc_node_lookup(self, toc_tree: list[dict]) -> dict[str, dict]:
        """Build lookup map for ToC nodes keyed by node_id."""
        lookup: dict[str, dict] = {}

        def walk(node: dict) -> None:
            node_id = node.get("node_id")
            if isinstance(node_id, str):
                node.setdefault("cross_references", [])
                lookup[node_id] = node
            for sub in node.get("sub_nodes", []):
                walk(sub)

        for root in toc_tree:
            walk(root)
        return lookup

    def _extract_section_id_from_para_id(self, para_id: str) -> str:
        """Extract section_id from para_id format {doc_id}:{section_id}:pXXX."""
        parts = para_id.split(":")
        if len(parts) >= 3:
            return parts[1]
        return ""

    def _normalize_section_label(self, section_id: str) -> str:
        """Normalize section id like s001.02 into 1.2."""
        normalized = section_id.lstrip("s")
        parts = [p for p in normalized.split(".") if p]
        if not parts:
            return ""
        normalized_parts = [str(int(part)) if part.isdigit() else part for part in parts]
        return ".".join(normalized_parts)

    def _resolve_cross_reference_target(
        self,
        target_hint: str | None,
        doc_id: str,
        node_lookup: dict[str, dict],
    ) -> tuple[str | None, str | None, bool]:
        """Resolve a target hint to a concrete section in the current document."""
        if not target_hint:
            return None, None, False

        hint = target_hint.strip()
        if not hint:
            return None, None, False

        by_section_number: dict[str, str] = {}
        by_appendix_letter: dict[str, str] = {}
        by_title: dict[str, str] = {}

        for node_id, node in node_lookup.items():
            by_title[str(node.get("title", "")).lower()] = node_id

            normalized_section = self._normalize_section_label(node_id)
            if normalized_section:
                by_section_number[normalized_section] = node_id

            title_lower = str(node.get("title", "")).lower()
            appendix_match = re.search(r"(?:appendix|anhang|annexe|allegato)\s+([a-z])", title_lower)
            if appendix_match:
                by_appendix_letter[appendix_match.group(1).upper()] = node_id

        if re.fullmatch(r"\d+(?:\.\d+)*", hint):
            normalized_hint = ".".join(str(int(part)) for part in hint.split("."))
            node_id = by_section_number.get(normalized_hint)
            if node_id:
                return doc_id, node_id, True

        if re.fullmatch(r"[A-Za-z]", hint):
            node_id = by_appendix_letter.get(hint.upper())
            if node_id:
                return doc_id, node_id, True

        hint_lower = hint.lower()
        for title, node_id in by_title.items():
            if hint_lower in title or title in hint_lower:
                return doc_id, node_id, True

        return None, None, False

    def _report_progress(
        self,
        callback: Callable[[str, float], None] | None,
        stage: str,
        progress: float,
    ) -> None:
        """Report progress via callback if provided.

        Args:
            callback: Progress callback function
            stage: Current stage name
            progress: Progress value (0.0 to 1.0)
        """
        if callback:
            callback(stage, progress)
