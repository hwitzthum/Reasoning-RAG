"""Integration tests for document ingestion pipeline.

Tests the complete ingestion workflow including parsing, structure analysis,
annotation, and storage.
"""

import pytest
from pathlib import Path
from sqlalchemy import select

from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.structure import MarkdownStructureAnalyzer
from app.storage.models import Document, Section, Paragraph
from app.storage.repositories import DocumentRepository


@pytest.mark.asyncio
async def test_ingest_policy_end_to_end(db_session, fixtures_dir):
    """Test complete ingestion of test_policy.md document.

    Verifies:
    - Document created in database
    - Correct section count and hierarchy
    - Paragraphs have correct para_ids
    - ToC JSON structure is valid
    """
    # Setup
    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    assert policy_path.exists(), f"Test fixture not found: {policy_path}"

    pipeline = IngestionPipeline(db_session)

    # Execute ingestion
    doc_id = await pipeline.ingest_document(policy_path)

    # Verify document created
    doc_repo = DocumentRepository(db_session)
    document = await doc_repo.get_by_id(doc_id)

    assert document is not None
    assert document.doc_id == doc_id
    assert document.title is not None
    assert document.file_type == "md"

    # Verify ToC JSON structure
    assert document.toc_json is not None
    assert isinstance(document.toc_json, list)
    assert len(document.toc_json) > 0

    # Verify each ToC node has required fields
    root_node = document.toc_json[0]
    assert "node_id" in root_node
    assert "title" in root_node
    assert "level" in root_node

    # Verify sections in database
    result = await db_session.execute(
        select(Section).where(Section.doc_id == doc_id)
    )
    sections = result.scalars().all()

    assert len(sections) > 0, "No sections created"

    # Verify section hierarchy
    root_sections = [s for s in sections if s.parent_section_id is None]
    assert len(root_sections) > 0, "No root sections found"

    # Verify paragraphs exist and have correct para_ids
    result = await db_session.execute(
        select(Paragraph).where(Paragraph.doc_id == doc_id)
    )
    paragraphs = result.scalars().all()

    assert len(paragraphs) > 0, "No paragraphs created"

    # Verify para_id format: {doc_id}:{section_id}:{para_index}
    for para in paragraphs:
        assert para.para_id.startswith(f"{doc_id}:")
        parts = para.para_id.split(":")
        assert len(parts) == 3
        assert parts[0] == doc_id
        assert parts[2].startswith("p")


@pytest.mark.asyncio
async def test_checkpoint_recovery(db_session, fixtures_dir):
    """Test checkpoint recovery after simulated failure.

    Simulates a failure during annotation stage and verifies that
    the pipeline can resume from the checkpoint.
    """
    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)

    # Mock annotator to fail on first call, succeed on second
    call_count = 0
    original_annotate = pipeline.annotator.annotate_section

    async def mock_annotate_with_failure(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Simulated annotation failure")
        return await original_annotate(*args, **kwargs)

    pipeline.annotator.annotate_section = mock_annotate_with_failure

    # First attempt should fail and create checkpoint
    with pytest.raises(Exception, match="Simulated annotation failure"):
        await pipeline.ingest_document(policy_path)

    # Verify checkpoint exists
    doc_id = policy_path.stem
    checkpoint = await pipeline.checkpoint_manager.get(doc_id)
    assert checkpoint is not None
    assert checkpoint.stage is not None

    # Second attempt should resume and succeed
    pipeline2 = IngestionPipeline(db_session)
    doc_id_resumed = await pipeline2.ingest_document(policy_path)

    assert doc_id_resumed == doc_id

    # Verify document was fully ingested
    doc_repo = DocumentRepository(db_session)
    document = await doc_repo.get_by_id(doc_id)
    assert document is not None

    # Verify checkpoint was cleared
    checkpoint_after = await pipeline2.checkpoint_manager.get(doc_id)
    assert checkpoint_after is None


@pytest.mark.asyncio
async def test_reingest_same_document(db_session, fixtures_dir):
    """Test re-ingesting the same document (file_hash deduplication).

    Note: Current implementation doesn't deduplicate by file_hash,
    so this test verifies that re-ingestion succeeds and creates
    a second entry (or updates the existing one).
    """
    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)

    # First ingestion
    doc_id_1 = await pipeline.ingest_document(policy_path)

    # Get first document
    doc_repo = DocumentRepository(db_session)
    doc_1 = await doc_repo.get_by_id(doc_id_1)
    assert doc_1 is not None

    # Second ingestion of same file
    doc_id_2 = await pipeline.ingest_document(policy_path)

    # Both should have same doc_id (from filename)
    assert doc_id_2 == doc_id_1

    # Verify document exists
    doc_2 = await doc_repo.get_by_id(doc_id_2)
    assert doc_2 is not None


@pytest.mark.asyncio
async def test_section_count_and_hierarchy(db_session, fixtures_dir):
    """Test that section count and hierarchy match ToC structure."""
    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)

    doc_id = await pipeline.ingest_document(policy_path)

    # Get document and sections
    doc_repo = DocumentRepository(db_session)
    document = await doc_repo.get_by_id(doc_id)

    result = await db_session.execute(
        select(Section).where(Section.doc_id == doc_id)
    )
    sections = result.scalars().all()

    # Count sections in ToC
    def count_toc_sections(nodes):
        count = 0
        for node in nodes:
            count += 1
            if node.get("sub_nodes"):
                count += count_toc_sections(node["sub_nodes"])
        return count

    toc_section_count = count_toc_sections(document.toc_json)

    # Verify section count matches
    assert len(sections) == toc_section_count

    # Verify hierarchy: each section with parent_section_id has a parent that exists
    section_ids = {s.section_id for s in sections}
    for section in sections:
        if section.parent_section_id is not None:
            assert section.parent_section_id in section_ids


@pytest.mark.asyncio
async def test_toc_json_structure(db_session, fixtures_dir, monkeypatch):
    """Test that ToC JSON has correct structure with all required fields."""
    # Mock the annotator to avoid real API calls
    mock_annotation = {
        "summary": "Test summary",
        "language": "en",
        "confidence": "high",
    }

    async def _mock_annotate_section(*args, **kwargs):
        return mock_annotation

    monkeypatch.setattr(
        "app.ingestion.annotator.HaikuAnnotator.annotate_section",
        _mock_annotate_section,
    )

    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)

    doc_id = await pipeline.ingest_document(policy_path)

    doc_repo = DocumentRepository(db_session)
    document = await doc_repo.get_by_id(doc_id)

    # Verify ToC structure recursively
    def verify_toc_node(node, depth=0):
        # Required fields
        assert "node_id" in node
        assert "title" in node
        assert "level" in node

        # Optional fields
        if "summary" in node:
            assert isinstance(node["summary"], str)

        if "page_range" in node:
            assert isinstance(node["page_range"], list)
            assert len(node["page_range"]) == 2

        if "paragraph_count" in node:
            assert isinstance(node["paragraph_count"], int)
            assert node["paragraph_count"] >= 0

        if "cross_references" in node:
            assert isinstance(node["cross_references"], list)

        # Verify sub_nodes recursively
        if "sub_nodes" in node:
            assert isinstance(node["sub_nodes"], list)
            for sub_node in node["sub_nodes"]:
                verify_toc_node(sub_node, depth + 1)

    for node in document.toc_json:
        verify_toc_node(node)


@pytest.mark.asyncio
async def test_paragraph_ids_format(db_session, fixtures_dir):
    """Test that all paragraphs have correctly formatted para_ids."""
    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)

    doc_id = await pipeline.ingest_document(policy_path)

    result = await db_session.execute(
        select(Paragraph).where(Paragraph.doc_id == doc_id)
    )
    paragraphs = result.scalars().all()

    assert len(paragraphs) > 0

    for para in paragraphs:
        # Format: {doc_id}:{section_id}:{para_index}
        parts = para.para_id.split(":")

        assert len(parts) == 3, f"Invalid para_id format: {para.para_id}"
        assert parts[0] == doc_id
        assert parts[1].startswith("s")  # section_id starts with 's'
        assert parts[2].startswith("p")  # para_index starts with 'p'

        # Verify consistency with database fields
        assert para.doc_id == doc_id
        assert para.section_id == parts[1]


@pytest.mark.asyncio
async def test_offline_annotation_detects_german_language(db_session, tmp_path):
    """Fallback annotation should detect German docs as DE in offline mode."""
    markdown = """# Datenschutz Richtlinie

Diese Richtlinie gilt fuer alle Mitarbeitenden in der Schweiz.

## Geltungsbereich

Der Zugriff erfolgt gemaess dem Prinzip der geringsten Rechte.
"""
    doc_path = tmp_path / "policy_de.md"
    doc_path.write_text(markdown, encoding="utf-8")

    pipeline = IngestionPipeline(db_session)
    pipeline.annotator.offline_mode = True

    doc_id = await pipeline.ingest_document(doc_path)

    doc_repo = DocumentRepository(db_session)
    document = await doc_repo.get_by_id(doc_id)
    assert document is not None
    assert document.language == "de"


def test_structure_analyzer_creates_synthetic_root_for_headingless_markdown():
    """Headingless docs should get a synthetic Full Document root section."""
    analyzer = MarkdownStructureAnalyzer()
    sections = analyzer.analyze("Paragraph one.\n\nParagraph two.")

    assert len(sections) == 1
    assert sections[0].section_id == "s000"
    assert sections[0].title == "Full Document"
