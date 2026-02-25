"""Phase 2 integration tests.

Covers:
- search_fallback behavior
- cross-reference resolution and unresolved tracking
- /ui template rendering routes
"""

from __future__ import annotations

from pathlib import Path
import hashlib

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.tools import ToolHandler
from app.ingestion.pipeline import IngestionPipeline
from app.main import app
from app.storage.database import get_db
from app.storage.models import CrossReference, Document, Paragraph


@pytest.fixture
async def client(db_session):
    """Async test client with DB dependency override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _collect_toc_cross_refs(nodes: list[dict]) -> list[dict]:
    """Collect cross-reference entries from all ToC nodes."""
    refs: list[dict] = []

    def walk(node: dict) -> None:
        refs.extend(node.get("cross_references", []))
        for sub in node.get("sub_nodes", []):
            walk(sub)

    for node in nodes:
        walk(node)

    return refs


@pytest.mark.asyncio
async def test_search_fallback_returns_results(db_session, fixtures_dir):
    """search_fallback should return relevant paragraph candidates."""
    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)
    doc_id = await pipeline.ingest_document(policy_path)

    tool_handler = ToolHandler(db_session)
    results = await tool_handler.execute(
        "search_fallback",
        {
            "query_text": "password",
            "doc_ids": [doc_id],
            "top_k": 5,
        },
    )

    assert isinstance(results, list)
    assert len(results) > 0
    first = results[0]
    assert "para_id" in first
    assert "text" in first
    assert "score" in first
    assert "doc_id" in first
    assert "section_path" in first
    assert all(item["doc_id"] == doc_id for item in results)


@pytest.mark.asyncio
async def test_cross_reference_resolution_tracks_resolved_and_unresolved(db_session, tmp_path):
    """Pipeline should resolve valid references and keep unresolved ones."""
    markdown = """# 1. Overview

See Section 1.1 for details and see Section 9.9 for legacy controls.

## 1.1 Controls

The control details are listed here.
"""
    sample_path = tmp_path / "phase2_crossref.md"
    sample_path.write_text(markdown, encoding="utf-8")

    pipeline = IngestionPipeline(db_session)
    doc_id = await pipeline.ingest_document(sample_path)

    xref_result = await db_session.execute(
        select(CrossReference).where(CrossReference.source_para_id.like(f"{doc_id}:%"))
    )
    xrefs = list(xref_result.scalars().all())

    assert len(xrefs) >= 2
    assert any(x.resolved for x in xrefs)
    assert any(not x.resolved for x in xrefs)

    resolved = [x for x in xrefs if x.resolved]
    assert all(x.target_doc_id == doc_id for x in resolved)
    assert all(x.target_node_id for x in resolved)

    para_result = await db_session.execute(
        select(Paragraph).where(Paragraph.doc_id == doc_id).order_by(Paragraph.para_index)
    )
    paragraphs = list(para_result.scalars().all())
    assert len(paragraphs) > 0

    # Verify cross-reference metadata also exists in toc_json payload
    from app.storage.repositories import DocumentRepository

    repo = DocumentRepository(db_session)
    document = await repo.get_by_id(doc_id)
    assert document is not None
    toc_refs = _collect_toc_cross_refs(document.toc_json)
    assert len(toc_refs) >= 2
    assert any(ref.get("resolved") is True for ref in toc_refs)
    assert any(ref.get("resolved") is False for ref in toc_refs)


@pytest.mark.asyncio
async def test_ui_routes_render_query_and_citation_panel(client, db_session, fixtures_dir):
    """UI routes should render HTML for query page and citation panel."""
    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)
    doc_id = await pipeline.ingest_document(policy_path)

    para_result = await db_session.execute(
        select(Paragraph).where(Paragraph.doc_id == doc_id).limit(1)
    )
    paragraph = para_result.scalar_one()

    ui_response = await client.get("/ui")
    assert ui_response.status_code == 200
    assert "text/html" in ui_response.headers.get("content-type", "")
    assert "Cross-Document Reasoning Console" in ui_response.text
    assert "<form" in ui_response.text

    citation_response = await client.get(f"/ui/citation/{paragraph.para_id}")
    assert citation_response.status_code == 200
    assert "text/html" in citation_response.headers.get("content-type", "")
    assert paragraph.para_id in citation_response.text
    assert "Source Evidence" in citation_response.text

    source_response = await client.get(f"/ui/source/{paragraph.para_id}")
    assert source_response.status_code == 200
    assert "text/html" in source_response.headers.get("content-type", "")
    assert "Source Passage" in source_response.text
    assert paragraph.para_id in source_response.text

    root_html_response = await client.get("/", headers={"accept": "text/html"})
    assert root_html_response.status_code == 307
    assert root_html_response.headers.get("location") == "/ui"


@pytest.mark.asyncio
async def test_ui_source_passage_includes_original_link_via_hash_fallback(client, db_session, tmp_path):
    """UI source passage should include full-document links via file-hash fallback."""
    original_documents_path = settings.documents_path
    settings.documents_path = tmp_path
    try:
        doc_id = "legacydoc01"
        source_dir = tmp_path / "legacy-folder"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_file = source_dir / "original.pdf"
        payload = b"%PDF-1.4\\nlegacy-source\\n"
        source_file.write_bytes(payload)
        file_hash = hashlib.sha256(payload).hexdigest()

        document = Document(
            doc_id=doc_id,
            title="Legacy Policy",
            file_type="pdf",
            language="en",
            total_pages=2,
            file_hash=file_hash,
            toc_json=[],
            summary="Legacy doc",
        )
        paragraph = Paragraph(
            para_id=f"{doc_id}:s001:p001",
            doc_id=doc_id,
            section_id="s001",
            para_index=1,
            text="Legacy paragraph",
            markdown_source="Legacy paragraph",
            page_number=2,
            section_path=["1. Legacy"],
        )
        db_session.add(document)
        db_session.add(paragraph)
        await db_session.commit()

        response = await client.get(f"/ui/source/{paragraph.para_id}")
        assert response.status_code == 200
        assert "Source Passage" in response.text
        assert f"/ui/source/{paragraph.para_id}?open_original=true" in response.text

        open_original_response = await client.get(
            f"/ui/source/{paragraph.para_id}?open_original=true",
            follow_redirects=False,
        )
        assert open_original_response.status_code == 307
        assert open_original_response.headers.get("location") == f"/api/documents/{doc_id}/original#page=2"
    finally:
        settings.documents_path = original_documents_path
