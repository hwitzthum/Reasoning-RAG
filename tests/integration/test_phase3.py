"""Phase 3 integration and calibration tests."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.routes import admin as admin_routes
from app.config import settings
from app.core.evidence import EvidenceVerifier, calculate_confidence
from app.main import app
from app.storage.cache import CacheManager
from app.storage.database import get_db
from app.storage.models import Document, QueryCache, QueryLog, ReasoningTrace
from tests.fixtures.test_questions import TEST_QUESTIONS_50


@pytest.fixture
async def client(db_session):
    """Async test client with DB dependency override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def restore_runtime_settings():
    """Restore mutable runtime settings after each test that changes them."""
    snapshot = {
        "max_reasoning_iterations": settings.max_reasoning_iterations,
        "query_timeout_seconds": settings.query_timeout_seconds,
        "log_level": settings.log_level,
        "dry_run_cache_only": settings.dry_run_cache_only,
        "query_cache_ttl_seconds": settings.query_cache_ttl_seconds,
    }
    yield
    for key, value in snapshot.items():
        setattr(settings, key, value)


def test_phase3_question_bank_distribution():
    """Question bank contains 50 entries with required category distribution."""
    assert len(TEST_QUESTIONS_50) == 50

    categories = {}
    languages = set()
    for q in TEST_QUESTIONS_50:
        categories[q["category"]] = categories.get(q["category"], 0) + 1
        languages.add(q["language"])
        assert "expected_source" in q
        assert "expected_keywords" in q

    assert categories["factual_single_doc"] == 15
    assert categories["factual_specific_section"] == 10
    assert categories["synthesis_single_doc"] == 8
    assert categories["synthesis_cross_doc"] == 7
    assert categories["cross_reference_following"] == 5
    assert categories["unanswerable"] == 5
    assert {"de", "fr", "it", "en"}.issubset(languages)


def test_calculate_confidence_calibration_rules():
    """Confidence calibration respects diversity, depth, and unresolved xref penalties."""
    high = calculate_confidence(
        evidence_log=[
            {"para_id": "docA:s1:p001"},
            {"para_id": "docA:s2:p001"},
            {"para_id": "docB:s1:p001"},
        ],
        citations=[
            {"doc_title": "Policy A", "section": "1.0", "page": 1},
            {"doc_title": "Policy B", "section": "1.0", "page": 2},
        ],
    )
    assert high["level"] == "high"
    assert high["metrics"]["evidence_diversity"] >= 2

    medium_capped = calculate_confidence(
        evidence_log=[
            {"para_id": "docA:s1:p001"},
            {"para_id": "docA:s1:p002"},
            {"para_id": "docA:s2:p001"},
        ],
        citations=[
            {"doc_title": "Policy A", "section": "1.0", "page": 1},
            {"doc_title": "Policy A", "section": "2.0", "page": 2},
        ],
    )
    assert medium_capped["level"] == "medium"

    low_penalized = calculate_confidence(
        evidence_log=[
            {"para_id": "docA:s1:p001", "unresolved_cross_reference": True},
        ],
        citations=[{"doc_title": "Policy A", "section": "1.0", "page": 1}],
    )
    assert low_penalized["level"] == "low"
    assert low_penalized["metrics"]["unresolved_cross_references"] == 1


def test_multilingual_citation_extraction_and_verification():
    """German-style citations should be extracted and verified against section titles."""
    verifier = EvidenceVerifier()
    answer = (
        "Die Teuerung wird ausgeglichen. "
        "[Lohnreglement, Abschnitt 2.6.2 Teuerungsausgleich]"
    )

    citations = verifier.extract_citations(answer)
    assert len(citations) == 1
    assert citations[0]["doc_title"] == "Lohnreglement"
    assert citations[0]["section"] == "2.6.2"
    assert citations[0]["section_label"].startswith("Abschnitt")
    assert citations[0]["page"] is None

    verified, unverified = verifier.verify(
        citations,
        evidence_log=[
            {
                "para_id": "doc123:s14:p001",
                "doc_title": "Lohnreglement",
                "section_id": "s14",
                "section_title": "2.6.2 Teuerungsausgleich",
            }
        ],
    )

    assert len(verified) == 1
    assert len(unverified) == 0
    assert verified[0]["verified_para_id"] == "doc123:s14:p001"


def test_single_doc_verification_without_mapping_rejects_citation():
    """Single-document evidence must not auto-verify unmatched citations."""
    verifier = EvidenceVerifier()
    citations = verifier.extract_citations(
        "Antwort. [Lohnreglement, Abschnitt 2.6.2 Teuerungsausgleich]"
    )
    verified, unverified = verifier.verify(
        citations,
        evidence_log=[{"para_id": "docsolo:s99:p001"}],
    )
    assert len(verified) == 0
    assert len(unverified) == 1


def test_para_id_citation_format_is_extracted_and_verified():
    """Direct para_id citation format should produce verified citations."""
    verifier = EvidenceVerifier()
    citations = verifier.extract_citations(
        "Quelle siehe [original:s14:p001] fuer die Aussage."
    )
    assert len(citations) == 1
    assert citations[0]["para_id"] == "original:s14:p001"

    verified, unverified = verifier.verify(
        citations,
        evidence_log=[{"para_id": "original:s14:p001"}],
    )
    assert len(verified) == 1
    assert len(unverified) == 0
    assert verified[0]["verified_para_id"] == "original:s14:p001"


def test_extended_swiss_citation_labels_are_extracted():
    """Citation extractor should support legal/policy labels used in Swiss docs."""
    verifier = EvidenceVerifier()
    answer = (
        "Referenzen: [Reglement, Art. 5 Datenschutz], [Reglement, § 3 Zugriff], "
        "[Reglement, Alinéa 2 Zuständigkeit], [Reglement, Chiffre 4.1 Prozesse]"
    )
    citations = verifier.extract_citations(answer)
    labels = [item["section_label"] for item in citations]

    assert len(citations) == 4
    assert any(label.startswith("Art.") for label in labels)
    assert any(label.startswith("§") for label in labels)
    assert any(label.startswith("Alinéa") for label in labels)
    assert any(label.startswith("Chiffre") for label in labels)


@pytest.mark.asyncio
async def test_phase3_admin_api_and_pages(client, db_session, tmp_path, monkeypatch):
    """Admin API and page routes should render and expose expected Phase 3 UX elements."""
    eval_dir = tmp_path / "evaluation_runs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    sample_run = {
        "run_id": "test_run",
        "timestamp": "2026-02-22T00:00:00Z",
        "metrics": {
            "accuracy": 0.9,
            "citation_accuracy": 0.8,
            "total_questions": 50,
            "passed_questions": 45,
            "avg_iterations": 2,
            "avg_latency_ms": 123.0,
        },
        "results": [
            {
                "id": "Q-001",
                "question": "What is the password requirement?",
                "expected_source": "Password Policy",
                "expected_keywords": ["password", "12"],
                "answer": "Passwords require at least 12 characters.",
                "passed": True,
                "confidence": "high",
                "latency_ms": 12.0,
            }
        ],
    }
    (eval_dir / "evaluation_test.json").write_text(json.dumps(sample_run), encoding="utf-8")
    monkeypatch.setattr(admin_routes, "EVAL_RUNS_DIR", eval_dir)
    monkeypatch.setattr(admin_routes, "CONFIG_AUDIT_FILE", tmp_path / "config_audit.log")

    doc = Document(
        doc_id="admintest001",
        title="Admin Test Document",
        file_type="md",
        language="en",
        total_pages=1,
        file_hash="hash-admin-test",
        toc_json=[{"node_id": "s1", "title": "Root", "level": 1, "sub_nodes": [], "cross_references": []}],
        summary="Admin seed document",
    )
    db_session.add(doc)
    db_session.add(
        QueryLog(
            query_id="q-admin-1",
            query_text="test query",
            cache_hit=True,
            latency_ms=25,
            iterations=2,
            confidence="medium",
            created_at=datetime(2026, 2, 21, 12, 0, 0),
        )
    )
    db_session.add(
        QueryCache(
            query_hash="hash-q-admin-1",
            query_text="test query",
            doc_scope=["admintest001"],
            answer="answer",
            confidence="medium",
            citations=[],
            evidence_log=[],
            sections_explored=[],
            iterations=2,
        )
    )
    db_session.add(
        ReasoningTrace(
            query_id="q-admin-1",
            query_text="test query",
            trace_json=[
                {"type": "user", "message": "test query"},
                {"type": "tool_call", "name": "read_section", "iteration": 1, "duration_ms": 2.5},
                {"type": "tool_result", "name": "read_section", "node_id": "s1", "duration_ms": 4.5},
                {"type": "assistant", "message": "final"},
            ],
            answer="Policy states 12 chars [Password Policy, Section 2.1, p.5]",
            latency_ms=25,
            iterations=2,
        )
    )
    await db_session.commit()

    stats = await client.get("/api/admin/cache/stats")
    assert stats.status_code == 200
    assert "l4_hit_rate" in stats.json()

    recent = await client.get("/api/admin/queries/recent?date_from=2026-02-21&date_to=2026-02-21")
    assert recent.status_code == 200
    assert len(recent.json()) >= 1
    assert recent.json()[0]["query_id"] == "q-admin-1"

    trace = await client.get("/api/admin/traces/q-admin-1")
    assert trace.status_code == 200
    assert trace.json()["query_id"] == "q-admin-1"

    cfg_put = await client.put(
        "/api/admin/config",
        json={
            "max_reasoning_iterations": settings.max_reasoning_iterations,
            "query_timeout_seconds": settings.query_timeout_seconds,
            "log_level": settings.log_level,
            "dry_run_cache_only": settings.dry_run_cache_only,
            "query_cache_ttl_seconds": settings.query_cache_ttl_seconds,
        },
    )
    assert cfg_put.status_code == 200

    eval_page = await client.get("/admin/evaluation")
    assert eval_page.status_code == 200
    assert "Evaluation Runs" in eval_page.text
    assert "eval-trend-chart" in eval_page.text
    assert "Question Drill-Down" in eval_page.text

    documents_page = await client.get("/admin/documents")
    assert documents_page.status_code == 200
    assert "Document Management" in documents_page.text
    assert "upload-dropzone" in documents_page.text
    assert "delete-modal" in documents_page.text

    cache_page = await client.get("/admin/cache")
    assert cache_page.status_code == 200
    assert "Cache Statistics" in cache_page.text
    assert "dry_run_cache_only" in cache_page.text
    assert "query_cache_ttl_seconds" in cache_page.text

    queries_page = await client.get("/admin/queries?date_from=2026-02-21&date_to=2026-02-21")
    assert queries_page.status_code == 200
    assert "Query Log Viewer" in queries_page.text
    assert "Date From" in queries_page.text
    assert "Sections explored" in queries_page.text

    trace_page = await client.get("/admin/trace/q-admin-1")
    assert trace_page.status_code == 200
    assert "Reasoning Trace" in trace_page.text
    assert "trace-timeline" in trace_page.text
    assert "citation-highlight" in trace_page.text

    config_page = await client.get("/admin/config")
    assert config_page.status_code == 200
    assert "Runtime Settings" in config_page.text

    trace_q = await db_session.execute(select(ReasoningTrace).where(ReasoningTrace.query_id == "q-admin-1"))
    assert trace_q.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_phase3_cache_invalidation_matches_verified_para_ids(db_session):
    """Cache invalidation should drop entries citing a document via verified_para_id."""
    cache_manager = CacheManager(db_session)

    db_session.add_all(
        [
            QueryCache(
                query_hash="hash-invalidate-hit",
                query_text="invalidate hit",
                doc_scope=None,
                answer="hit",
                confidence="high",
                citations=[
                    {
                        "doc_title": "Policy",
                        "section": "1.0",
                        "page": 1,
                        "verified_para_id": "doc_target:s001:p001",
                    }
                ],
                evidence_log=[],
                sections_explored=[],
                iterations=1,
            ),
            QueryCache(
                query_hash="hash-invalidate-miss",
                query_text="invalidate miss",
                doc_scope=None,
                answer="miss",
                confidence="low",
                citations=[
                    {
                        "doc_title": "Other",
                        "section": "1.0",
                        "page": 1,
                        "verified_para_id": "doc_other:s001:p001",
                    }
                ],
                evidence_log=[],
                sections_explored=[],
                iterations=1,
            ),
        ]
    )
    await db_session.commit()

    await cache_manager.invalidate_for_document("doc_target")

    remaining = (await db_session.execute(select(QueryCache))).scalars().all()
    remaining_hashes = {entry.query_hash for entry in remaining}

    assert "hash-invalidate-hit" not in remaining_hashes
    assert "hash-invalidate-miss" in remaining_hashes


@pytest.mark.asyncio
async def test_phase3_cache_invalidation_matches_evidence_log_para_ids(db_session):
    """Cache invalidation should drop entries tied to a doc via evidence_log para_ids."""
    cache_manager = CacheManager(db_session)

    db_session.add_all(
        [
            QueryCache(
                query_hash="hash-evidence-hit",
                query_text="evidence hit",
                doc_scope=None,
                answer="hit",
                confidence="medium",
                citations=[],
                evidence_log=[{"para_id": "doc_target:s014:p001"}],
                sections_explored=[],
                iterations=1,
            ),
            QueryCache(
                query_hash="hash-evidence-miss",
                query_text="evidence miss",
                doc_scope=None,
                answer="miss",
                confidence="low",
                citations=[],
                evidence_log=[{"para_id": "doc_other:s001:p001"}],
                sections_explored=[],
                iterations=1,
            ),
        ]
    )
    await db_session.commit()

    await cache_manager.invalidate_for_document("doc_target")

    remaining = (await db_session.execute(select(QueryCache))).scalars().all()
    remaining_hashes = {entry.query_hash for entry in remaining}

    assert "hash-evidence-hit" not in remaining_hashes
    assert "hash-evidence-miss" in remaining_hashes


@pytest.mark.asyncio
async def test_phase3_query_filters_and_csv_export(client, db_session):
    """Query log date-range filters and CSV export should work with strict filters."""
    db_session.add_all(
        [
            QueryLog(
                query_id="q-filter-1",
                query_text="question in range",
                cache_hit=False,
                confidence="low",
                created_at=datetime(2026, 2, 21, 10, 0, 0),
            ),
            QueryLog(
                query_id="q-filter-2",
                query_text="question out of range",
                cache_hit=True,
                confidence="high",
                created_at=datetime(2026, 2, 19, 8, 0, 0),
            ),
        ]
    )
    await db_session.commit()

    api_filtered = await client.get(
        "/api/admin/queries/recent?date_from=2026-02-21&date_to=2026-02-21&cache_hit=false"
    )
    assert api_filtered.status_code == 200
    payload = api_filtered.json()
    assert len(payload) == 1
    assert payload[0]["query_id"] == "q-filter-1"

    page_filtered = await client.get(
        "/admin/queries?date_from=2026-02-21&date_to=2026-02-21&cache_hit=false"
    )
    assert page_filtered.status_code == 200
    assert "q-filter-1" in page_filtered.text
    assert "q-filter-2" not in page_filtered.text

    csv_export = await client.get(
        "/admin/queries?date_from=2026-02-21&date_to=2026-02-21&cache_hit=false&export=csv"
    )
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers.get("content-type", "")
    assert "q-filter-1" in csv_export.text
    assert "q-filter-2" not in csv_export.text


@pytest.mark.asyncio
async def test_phase3_cache_dry_run_behavior(client, db_session, restore_runtime_settings):
    """Dry-run cache-only mode should block misses and allow cached responses."""
    settings.dry_run_cache_only = True

    miss_response = await client.post("/api/query", json={"question": "uncached phase3 question"})
    assert miss_response.status_code == 503
    assert "Cache-only dry-run mode" in miss_response.json().get("detail", "")

    cache_manager = CacheManager(db_session)
    await cache_manager.cache_query_result(
        "cached phase3 question",
        None,
        {
            "answer": "Cached answer",
            "confidence": "medium",
            "citations": [],
            "evidence_log": [],
            "sections_explored": [],
            "iterations": 1,
        },
    )

    hit_response = await client.post("/api/query", json={"question": "cached phase3 question"})
    assert hit_response.status_code == 200
    payload = hit_response.json()
    assert payload["status"] == "cached"
    assert payload["cached"] is True
