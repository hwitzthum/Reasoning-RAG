"""Pytest configuration and fixtures for Reasoning-RAG tests."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.storage.models import Base
# NOTE: app.main created in Level 2 (L2-F-001)
from app.main import app


@pytest.fixture(autouse=True)
def reset_sse_app_status():
    """Reset SSE global app status to avoid cross-event-loop leakage in tests."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None


@pytest.fixture
async def db_session():
    """
    Create in-memory SQLite database for tests.

    Yields:
        AsyncSession: Async database session for testing
    """
    # Use connect_args to avoid greenlet spawn issues
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session

    # Cleanup
    await engine.dispose()


# NOTE: client fixture enabled in Level 2 when app.main is created
@pytest.fixture
async def client(db_session):
    """
    Create async HTTP client for FastAPI testing.

    Args:
        db_session: Database session fixture

    Yields:
        AsyncClient: HTTP client for testing FastAPI endpoints
    """
    # Override database dependency
    from app.storage.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def mock_anthropic_client(monkeypatch):
    """
    Mock Anthropic API client for testing.

    Patches Anthropic at the orchestrator module level so all instances
    created during tests use the mock. Provides sensible default responses
    that yield valid answers with proper citation format.

    Args:
        monkeypatch: Built-in pytest monkeypatch fixture

    Returns:
        Mock: Configured mock Anthropic client instance
    """
    from unittest.mock import AsyncMock, Mock
    from anthropic.types import Message, TextBlock

    # Create mock client instance
    mock_instance = Mock()

    def _answer_for_question(question: str) -> str:
        q = question.lower()
        if "minimum password length" in q or "password length" in q:
            return "The minimum password length is 12 characters. [Password Policy, Section 2.1, p.5]"
        if "how often must passwords be rotated" in q:
            return "Passwords must be rotated every 90 days per rotation policy. [Password Policy, Section 2.2, p.6]"
        if "three user roles" in q:
            return "The roles are standard user, power user, and administrator. [Access Control Policy, Section 3.1, p.7]"
        if "least privilege" in q:
            return "Least privilege means granting only the access required for a task. [Access Control Policy, Section 3.0, p.7]"
        if "where are audit logs mentioned" in q:
            return "Audit logs are documented in Appendix A. [Appendix Logging Policy, Section 1.0, p.10]"
        if "how long are audit logs retained" in q:
            return "Audit logs are retained for 12 months. [Appendix Logging Policy, Section 1.0, p.10]"
        if "password complexity requirements" in q:
            return "Passwords require uppercase, lowercase, a number, and a special character. [Password Policy, Section 2.1, p.5]"
        if "who has full system access" in q:
            return "Administrators have full system access. [Access Control Policy, Section 3.1, p.7]"
        if "violates this policy" in q:
            return "Policy violations can lead to disciplinary action up to termination. [Enforcement Policy, Section 3.2, p.8]"
        if "who reviews the audit logs" in q:
            return "The security team reviews audit logs quarterly. [Appendix Logging Policy, Section 1.0, p.10]"
        return "Based on the policy documents, passwords must be at least 12 characters long. [Password Policy, Section 2.1, p.5]"

    async def _mock_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        question = ""
        for message in messages:
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                question = message["content"]
                break

        response = Mock(spec=Message)
        response.stop_reason = "end_turn"
        response.content = [TextBlock(type="text", text=_answer_for_question(question))]
        return response

    mock_instance.messages.create = AsyncMock(side_effect=_mock_create)

    # Patch at all locations where AsyncAnthropic is imported
    monkeypatch.setattr("app.core.orchestrator.AsyncAnthropic", lambda *args, **kwargs: mock_instance)
    monkeypatch.setattr("app.core.evidence.AsyncAnthropic", lambda *args, **kwargs: mock_instance)
    # In mocked mode we treat extracted citations as verified and deterministic high confidence.
    def _verify_mock(_self, citations, evidence_log):
        para_id = "mock_doc:s1:p001"
        if evidence_log and isinstance(evidence_log, list):
            first = evidence_log[0]
            if isinstance(first, dict) and first.get("para_id"):
                para_id = first["para_id"]

        verified = []
        for citation in citations:
            normalized = dict(citation)
            normalized["verified_para_id"] = normalized.get("verified_para_id", para_id)
            verified.append(normalized)
        return verified, []

    monkeypatch.setattr("app.core.orchestrator.EvidenceVerifier.verify", _verify_mock)
    monkeypatch.setattr(
        "app.core.orchestrator.calculate_confidence",
        lambda *args, **kwargs: {
            "level": "high",
            "statement": "Confidence: High - deterministic mocked test mode",
        },
    )

    return mock_instance


@pytest.fixture(autouse=True)
def force_annotator_offline(monkeypatch):
    """Force HaikuAnnotator into offline mode for all tests.

    Patches annotate_section at the class level so any IngestionPipeline created
    in tests never makes real Haiku API calls. Tests that need specific annotation
    behaviour can override at the instance level (instance attributes take precedence
    over the class-level patch) or re-patch via monkeypatch in the test body.
    """
    from app.ingestion.annotator import HaikuAnnotator

    async def _offline(self, title: str, content: str, context: str = "") -> dict:
        return self._get_fallback_annotation(title, content)

    monkeypatch.setattr(HaikuAnnotator, "annotate_section", _offline)


@pytest.fixture
def sample_markdown():
    """
    Sample Markdown document with heading structure.

    Returns:
        str: Sample Markdown content for testing structure analysis
    """
    return """# 1. Introduction

This is the introduction section of the test document. It contains important background information about the policy.

## 1.1 Purpose

The purpose of this document is to establish clear guidelines for information security within the organization.

## 1.2 Scope

This policy applies to all employees, contractors, and third-party partners who have access to organizational resources.

# 2. Password Security

Passwords are the first line of defense against unauthorized access.

## 2.1 Password Requirements

All passwords must meet the following requirements:
- Minimum 12 characters in length
- Include uppercase and lowercase letters
- Include at least one number
- Include at least one special character

## 2.2 Password Rotation

Passwords must be rotated every 90 days. See Section 3.2 for enforcement procedures.

# 3. Access Control

Access to systems and data must be controlled based on the principle of least privilege.

## 3.1 User Roles

The organization recognizes three user roles:
- Standard users: Limited access to basic resources
- Power users: Access to department-specific tools
- Administrators: Full system access

## 3.2 Enforcement

Violations of this policy may result in disciplinary action, up to and including termination. Gemäss Appendix A, the security team maintains audit logs.

# Appendix A: Audit Logging

All access attempts are logged and retained for a period of 12 months. The security team reviews these logs quarterly to identify suspicious activity.
"""


@pytest.fixture
def sample_markdown_multilingual():
    """
    Sample Markdown document with multilingual content and cross-references.

    Returns:
        str: Multilingual sample with German, French, Italian content
    """
    return """# 1. Sicherheitsrichtlinien

Dieses Dokument definiert die Sicherheitsrichtlinien für die Organisation.

## 1.1 Passwortanforderungen

Alle Passwörter müssen mindestens 12 Zeichen lang sein. Siehe Abschnitt 2.1 für Details.

## 1.2 Zugriffskontrolle

Der Zugriff erfolgt gemäss dem Prinzip der geringsten Rechte.

# 2. Politiques de Sécurité

Ce document définit les politiques de sécurité pour l'organisation.

## 2.1 Exigences de Mot de Passe

Tous les mots de passe doivent comporter au moins 12 caractères. Voir chapitre 1.1 pour référence.

## 2.2 Contrôle d'Accès

L'accès est accordé selon le principe du moindre privilège.

# 3. Politiche di Sicurezza

Questo documento definisce le politiche di sicurezza per l'organizzazione.

## 3.1 Requisiti Password

Tutte le password devono essere lunghe almeno 12 caratteri. Vedi sezione 1.1 per dettagli.

## 3.2 Controllo Accesso

L'accesso è concesso secondo il principio del minimo privilegio. Secondo Allegato B, tutti gli accessi sono registrati.

# Allegato B: Registro degli Accessi

Tutti i tentativi di accesso vengono registrati e conservati per 12 mesi.
"""


@pytest.fixture
def fixtures_dir():
    """
    Path to test fixtures directory.

    Returns:
        Path: Path to tests/fixtures directory
    """
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_documents_dir(fixtures_dir):
    """
    Path to sample documents directory.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Path to tests/fixtures/sample_documents directory
    """
    return fixtures_dir / "sample_documents"


@pytest.fixture
def mock_responses_dir(fixtures_dir):
    """
    Path to mock responses directory.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Path to tests/fixtures/mock_responses directory
    """
    return fixtures_dir / "mock_responses"
