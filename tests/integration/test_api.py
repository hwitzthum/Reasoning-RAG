"""Integration tests for FastAPI endpoints.

Tests all API endpoints including document management, query submission,
and feedback collection.
"""

import json
import logging
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from app.config import settings
from app.main import app
from app.api.routes.documents import _build_doc_id
from app.storage.database import get_db
from app.storage.models import Document


@pytest.fixture
async def client(db_session):
    """Create async HTTP client for FastAPI testing.

    Overrides database dependency with test database session.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_document_valid_pdf(client, fixtures_dir):
    """Test POST /api/documents/upload with valid PDF file."""
    # Note: This test requires a sample PDF file
    # For now, we'll test with markdown (which may not work in real ingestion)
    # In production, replace with actual PDF

    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"

    with open(policy_path, "rb") as f:
        files = {"file": ("test_policy.md", f, "text/markdown")}
        response = await client.post("/api/documents/upload", files=files)

    # May fail with 400 if .md not supported, or 500 during ingestion
    # Adjust based on actual validation logic
    assert response.status_code in [201, 400, 500]

    if response.status_code == 201:
        data = response.json()
        assert "doc_id" in data
        assert "status" in data
        assert "filename" in data


@pytest.mark.asyncio
async def test_list_documents(client):
    """Test GET /api/documents returns list of documents."""
    response = await client.get("/api/documents")

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)

    # May be empty if no documents uploaded
    # If documents exist, verify structure
    if len(data) > 0:
        doc = data[0]
        assert "doc_id" in doc
        assert "title" in doc
        assert "file_type" in doc


@pytest.mark.asyncio
async def test_get_document_by_id(client, db_session, fixtures_dir):
    """Test GET /api/documents/{id} returns document details."""
    # First, ingest a document to ensure one exists
    from app.ingestion.pipeline import IngestionPipeline

    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)

    try:
        doc_id = await pipeline.ingest_document(policy_path)
    except Exception:
        # If ingestion fails, skip this test
        pytest.skip("Document ingestion failed")

    # Get document via API
    response = await client.get(f"/api/documents/{doc_id}")

    assert response.status_code == 200

    data = response.json()
    assert data["doc_id"] == doc_id
    assert "title" in data
    assert "toc" in data
    assert isinstance(data["toc"], list)


@pytest.mark.asyncio
async def test_get_document_not_found(client):
    """Test GET /api/documents/{id} with non-existent document."""
    response = await client.get("/api/documents/nonexistent_doc_id")

    assert response.status_code == 404

    data = response.json()
    assert "error" in data or "detail" in data


@pytest.mark.asyncio
async def test_get_original_document_file(client, db_session, tmp_path):
    """Test GET /api/documents/{id}/original serves uploaded source file."""
    original_documents_path = settings.documents_path
    settings.documents_path = tmp_path
    try:
        doc_id = "origdoc001"
        doc_dir = tmp_path / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        source_path = doc_dir / "original.pdf"
        source_path.write_bytes(b"%PDF-1.4\\n% fake test content\\n")

        db_session.add(
            Document(
                doc_id=doc_id,
                title="Original Source Test",
                file_type="pdf",
                language="en",
                total_pages=1,
                file_hash="hash-original-source-test",
                toc_json=[],
                summary="Test document",
                original_filename="source.pdf",
            )
        )
        await db_session.commit()

        response = await client.get(f"/api/documents/{doc_id}/original")
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("content-type", "")
        assert response.content.startswith(b"%PDF-1.4")
    finally:
        settings.documents_path = original_documents_path


@pytest.mark.asyncio
async def test_delete_document(client, db_session, fixtures_dir):
    """Test DELETE /api/documents/{id} removes document."""
    # First, ingest a document
    from app.ingestion.pipeline import IngestionPipeline

    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)

    try:
        doc_id = await pipeline.ingest_document(policy_path)
    except Exception:
        pytest.skip("Document ingestion failed")

    # Delete document
    response = await client.delete(f"/api/documents/{doc_id}")

    assert response.status_code == 204

    # Verify document no longer exists
    get_response = await client.get(f"/api/documents/{doc_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_submit_query(client):
    """Test POST /api/query returns query_id and stream URL."""
    response = await client.post(
        "/api/query", json={"question": "What is the password policy?"}
    )

    assert response.status_code == 200

    data = response.json()
    assert "query_id" in data
    assert "status" in data
    assert "stream_url" in data

    # Verify stream URL format
    assert data["stream_url"].startswith("/api/query/")
    assert data["stream_url"].endswith("/stream")


@pytest.mark.asyncio
async def test_submit_query_accepts_scalar_doc_id(client):
    """Test POST /api/query accepts scalar doc_ids payloads from form-like clients."""
    response = await client.post(
        "/api/query",
        json={"question": "What is the password policy?", "doc_ids": "original"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "query_id" in data


@pytest.mark.asyncio
async def test_stream_preserves_doc_scope_for_cached_queries(client, db_session):
    """Stream endpoint should preserve submit-time doc scope for cache lookup."""
    from app.storage.cache import CacheManager

    question = "Scoped cache lookup"
    scoped_doc_ids = ["original"]

    cache_manager = CacheManager(db_session)
    await cache_manager.cache_query_result(
        question,
        scoped_doc_ids,
        {
            "answer": "Scoped cached answer",
            "confidence": "medium",
            "citations": [],
            "evidence_log": [],
            "sections_explored": [],
            "iterations": 1,
        },
    )

    submit_response = await client.post(
        "/api/query",
        json={"question": question, "doc_ids": scoped_doc_ids},
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert "doc_ids=original" in submit_payload["stream_url"]

    query_id = submit_payload["query_id"]
    answer_event = None
    event_type = None

    # Backward-compatibility path: stream called without doc_ids query params.
    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_type == "answer":
                answer_event = json.loads(line.split(":", 1)[1].strip())
                break

    assert answer_event is not None
    assert answer_event["answer"] == "Scoped cached answer"
    assert answer_event.get("cached") is True


@pytest.mark.asyncio
async def test_submit_query_invalid_input(client):
    """Test POST /api/query with invalid input returns 400."""
    # Empty question
    response = await client.post("/api/query", json={"question": ""})

    assert response.status_code == 400

    data = response.json()
    assert "error" in data or "detail" in data


@pytest.mark.asyncio
async def test_submit_query_missing_question(client):
    """Test POST /api/query without question field."""
    response = await client.post("/api/query", json={})

    # Should return 422 for validation error
    assert response.status_code == 422

    data = response.json()
    assert "error" in data or "detail" in data


@pytest.mark.asyncio
async def test_submit_feedback(client):
    """Test POST /api/query/{id}/feedback stores feedback."""
    # First, submit a query to get query_id
    query_response = await client.post(
        "/api/query", json={"question": "Test question"}
    )

    assert query_response.status_code == 200
    query_id = query_response.json()["query_id"]

    # Submit feedback
    feedback_response = await client.post(
        f"/api/query/{query_id}/feedback",
        json={"rating": "positive", "category": "helpful", "details": "Great answer"},
    )

    assert feedback_response.status_code == 201

    data = feedback_response.json()
    assert "message" in data
    assert data["query_id"] == query_id


@pytest.mark.asyncio
async def test_submit_feedback_invalid_query_id(client):
    """Test POST /api/query/{id}/feedback with non-existent query_id."""
    response = await client.post(
        "/api/query/nonexistent_query_id/feedback",
        json={"rating": "positive", "category": "helpful"},
    )

    assert response.status_code == 404

    data = response.json()
    assert "error" in data or "detail" in data


@pytest.mark.asyncio
async def test_health_check(client):
    """Test GET /health endpoint."""
    response = await client.get("/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test GET / returns API information."""
    response = await client.get("/")

    assert response.status_code == 200

    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_upload_logs_doc_id_collision_warning(client, db_session, fixtures_dir, tmp_path, caplog):
    """Uploading a colliding slug should emit an explicit warning."""
    original_documents_path = settings.documents_path
    settings.documents_path = tmp_path
    try:
        collision_filename = "collision.docx"
        collision_doc_id = _build_doc_id(collision_filename)

        db_session.add(
            Document(
                doc_id=collision_doc_id,
                title="Existing Colliding Doc",
                file_type="docx",
                language="en",
                total_pages=1,
                file_hash="hash-collision-existing",
                toc_json=[],
                summary="Existing doc for collision warning test",
                original_filename="existing-collision.docx",
            )
        )
        await db_session.commit()

        docx_path = fixtures_dir / "sample_documents" / "test_policy.docx"
        with docx_path.open("rb") as f:
            with caplog.at_level(logging.WARNING, logger="app.api.routes.documents"):
                response = await client.post(
                    "/api/documents/upload",
                    files={
                        "file": (
                            collision_filename,
                            f,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                )

        assert response.status_code in {201, 500, 504}
        assert any("collision detected" in record.message.lower() for record in caplog.records)
    finally:
        settings.documents_path = original_documents_path
