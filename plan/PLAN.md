# Implementation Plan: Reasoning-RAG

**Version:** 1.0
**Date:** 2026-02-22
**Status:** Ready for Implementation
**Reference:** `plan/SPEC.md` (Architecture Specification v2.0)

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Dependencies](#2-dependencies)
3. [Database Schema](#3-database-schema)
4. [Phase 1: MVP Implementation](#4-phase-1-mvp-implementation)
5. [Phase 2: Multi-Document Reasoning](#5-phase-2-multi-document-reasoning)
6. [Phase 3: Production System](#6-phase-3-production-system)
7. [Tool Implementations](#7-tool-implementations)
8. [Orchestrator Design](#8-orchestrator-design)
9. [Ingestion Pipeline](#9-ingestion-pipeline)
10. [Caching Implementation](#10-caching-implementation)
11. [API Endpoints](#11-api-endpoints)
12. [Testing Strategy](#12-testing-strategy)
13. [Development Guidelines](#13-development-guidelines)

---

## 1. Project Structure

```
reasoning_rag/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app entry point
│   ├── config.py                   # Settings and configuration (pydantic-settings)
│   ├── dependencies.py             # Dependency injection
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── query.py            # POST /query, GET /query/{id}/stream
│   │   │   ├── documents.py        # Document management endpoints
│   │   │   └── admin.py            # Admin endpoints (Phase 3)
│   │   └── schemas.py              # Pydantic request/response models
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # Reasoning orchestrator (Claude Sonnet)
│   │   ├── tools.py                # 7 tools implementation
│   │   ├── prompts.py              # System prompts and templates
│   │   └── evidence.py             # Evidence tracking and verification
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── pipeline.py             # Main ingestion pipeline coordinator
│   │   ├── docling_parser.py       # Docling wrapper for PDF/DOCX/PPTX
│   │   ├── structure.py            # Markdown structure analysis
│   │   ├── annotator.py            # Haiku annotation (summaries, language)
│   │   ├── cross_references.py     # Cross-reference extraction and indexing
│   │   └── checkpoints.py          # Checkpoint-based recovery
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py             # SQLite setup and connection
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   ├── repositories.py         # Data access layer (CRUD operations)
│   │   └── cache.py                # Cache layer implementations (L1-L5)
│   │
│   └── ui/
│       ├── __init__.py
│       ├── templates/              # Jinja2 HTML templates (Phase 2)
│       │   ├── base.html
│       │   ├── index.html
│       │   ├── query.html
│       │   └── admin/
│       │       ├── documents.html
│       │       └── monitoring.html
│       └── static/                 # CSS, minimal JS (Phase 2)
│           ├── css/
│           │   └── styles.css
│           └── js/
│               └── htmx.min.js
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_tools.py
│   │   ├── test_structure.py
│   │   ├── test_annotator.py
│   │   └── test_evidence.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_ingestion.py
│   │   ├── test_orchestrator.py
│   │   └── test_api.py
│   └── fixtures/
│       ├── sample_documents/       # Test PDF/DOCX files
│       └── mock_responses/         # Mock Anthropic API responses
│
├── documents/                      # Document storage (gitignored)
│   └── {doc_id}/
│       ├── original.*              # Original uploaded file
│       └── parsed.md               # Docling output
│
├── data/                           # SQLite database (gitignored)
│   └── reasoning_rag.db
│
├── plan/
│   ├── SPEC.md                     # Architecture specification
│   └── PLAN.md                     # This file
│
├── scripts/
│   ├── init_db.py                  # Database initialization
│   └── seed_test_data.py           # Optional test data seeding
│
├── pyproject.toml                  # Python project configuration
├── CLAUDE.md                       # Claude Code guidance
├── .gitignore
└── README.md
```

---

## 2. Dependencies

### pyproject.toml

```toml
[project]
name = "reasoning-rag"
version = "0.1.0"
description = "Reasoning-driven document QA system for Caritas Switzerland"
requires-python = ">=3.12"
dependencies = [
    # Web Framework
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "python-multipart>=0.0.18",          # File uploads
    "sse-starlette>=2.1.0",              # Server-Sent Events

    # LLM
    "anthropic>=0.42.0",                  # Claude API

    # Document Parsing
    "docling>=2.15.0",                    # PDF/DOCX/PPTX → Markdown

    # Database
    "sqlalchemy>=2.0.36",
    "aiosqlite>=0.20.0",                  # Async SQLite

    # Configuration
    "pydantic-settings>=2.6.0",

    # Templating (Phase 2)
    "jinja2>=3.1.4",

    # Utilities
    "python-dateutil>=2.9.0",
    "aiofiles>=24.1.0",                   # Async file operations
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",                      # Test client for FastAPI
    "ruff>=0.8.0",                        # Linting
    "mypy>=1.13.0",                       # Type checking
]

embeddings = [
    # Phase 2: Fallback search
    "sentence-transformers>=3.3.0",
    "faiss-cpu>=1.9.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
```

### Environment Variables

Create `.env` file (gitignored):

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional (defaults shown)
DATABASE_URL=sqlite+aiosqlite:///./data/reasoning_rag.db
DOCUMENTS_PATH=./documents
MAX_REASONING_ITERATIONS=8
QUERY_TIMEOUT_SECONDS=60
LOG_LEVEL=INFO
```

---

## 3. Database Schema

### SQLAlchemy Models (`app/storage/models.py`)

```python
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean,
    ForeignKey, JSON, Index, LargeBinary
)
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class Document(Base):
    """Stored documents with metadata."""
    __tablename__ = "documents"

    doc_id = Column(String(12), primary_key=True)  # UUID short form
    title = Column(String(500), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf, docx, pptx
    language = Column(String(5), nullable=False)    # de, fr, it, en
    total_pages = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256
    toc_json = Column(JSON, nullable=False)         # Full ToC tree
    summary = Column(Text)                          # Document-level summary
    original_filename = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sections = relationship("Section", back_populates="document", cascade="all, delete-orphan")
    paragraphs = relationship("Paragraph", back_populates="document", cascade="all, delete-orphan")

class Section(Base):
    """Document sections (ToC nodes)."""
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(String(50), nullable=False)  # e.g., "s001.1"
    doc_id = Column(String(12), ForeignKey("documents.doc_id", ondelete="CASCADE"))
    parent_section_id = Column(String(50))           # For hierarchy
    title = Column(String(500), nullable=False)
    summary = Column(Text)                           # Haiku-generated
    page_start = Column(Integer)
    page_end = Column(Integer)
    heading_level = Column(Integer)                  # 1, 2, 3
    section_path = Column(JSON)                      # ["1. Intro", "1.1 Scope"]

    document = relationship("Document", back_populates="sections")

    __table_args__ = (
        Index("ix_sections_doc_section", "doc_id", "section_id", unique=True),
    )

class Paragraph(Base):
    """Individual paragraphs with full provenance."""
    __tablename__ = "paragraphs"

    para_id = Column(String(100), primary_key=True)  # doc_id:section_id:p001
    doc_id = Column(String(12), ForeignKey("documents.doc_id", ondelete="CASCADE"))
    section_id = Column(String(50), nullable=False)
    para_index = Column(Integer, nullable=False)     # 1-based
    text = Column(Text, nullable=False)
    markdown_source = Column(Text)                   # Original markdown
    page_number = Column(Integer)                    # PDF physical page
    section_path = Column(JSON)                      # ["1. Intro", "1.1 Scope"]

    document = relationship("Document", back_populates="paragraphs")

    __table_args__ = (
        Index("ix_paragraphs_doc_section", "doc_id", "section_id"),
        Index("ix_paragraphs_text_fts", "text"),     # For grep_documents
    )

class CrossReference(Base):
    """Cross-reference index between sections/documents."""
    __tablename__ = "cross_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_para_id = Column(String(100), ForeignKey("paragraphs.para_id", ondelete="CASCADE"))
    source_text = Column(Text, nullable=False)       # "see Appendix G"
    target_doc_id = Column(String(12))               # Resolved target
    target_node_id = Column(String(50))              # Resolved section
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_crossref_source", "source_para_id"),
        Index("ix_crossref_target", "target_doc_id", "target_node_id"),
    )

class QueryCache(Base):
    """L4: Query result cache."""
    __tablename__ = "query_cache"

    query_hash = Column(String(64), primary_key=True)  # SHA-256 of query + doc_scope
    query_text = Column(Text, nullable=False)
    doc_scope = Column(JSON)                           # List of doc_ids or null
    answer = Column(Text, nullable=False)
    confidence = Column(String(10))                    # high, medium, low
    citations = Column(JSON, nullable=False)
    evidence_log = Column(JSON)
    sections_explored = Column(JSON)
    iterations = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_query_cache_created", "created_at"),
    )

class ReasoningTrace(Base):
    """L5: Full reasoning trace for audit/debugging."""
    __tablename__ = "reasoning_traces"

    query_id = Column(String(36), primary_key=True)    # UUID
    query_text = Column(Text, nullable=False)
    trace_json = Column(JSON, nullable=False)          # Full tool call sequence
    answer = Column(Text)
    latency_ms = Column(Integer)
    iterations = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    # No TTL - forever retention for compliance

class QueryLog(Base):
    """Query logging for analytics."""
    __tablename__ = "query_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(36), nullable=False)
    query_text = Column(Text, nullable=False)
    user_language = Column(String(5))
    cache_hit = Column(Boolean, default=False)
    latency_ms = Column(Integer)
    iterations = Column(Integer)
    confidence = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)

class UserFeedback(Base):
    """User feedback on answers."""
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(36), nullable=False)
    rating = Column(String(10))                        # thumbs_up, thumbs_down
    category = Column(String(50))                      # wrong_answer, incomplete, bad_citation, other
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

# Phase 2: Embeddings
class Embedding(Base):
    """L3: Paragraph embeddings for fallback search."""
    __tablename__ = "embeddings"

    para_id = Column(String(100), ForeignKey("paragraphs.para_id", ondelete="CASCADE"), primary_key=True)
    vector = Column(LargeBinary, nullable=False)       # Serialized numpy array
    model_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class IngestionCheckpoint(Base):
    """Checkpoint for resumable ingestion."""
    __tablename__ = "ingestion_checkpoints"

    doc_id = Column(String(12), primary_key=True)
    stage = Column(String(50), nullable=False)         # parsing, structure, annotation, indexing
    stage_data = Column(JSON)                          # Stage-specific state
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## 4. Phase 1: MVP Implementation

**Goal:** Working end-to-end system for single-document factual QA.

### Week 1: Foundation

#### Day 1-2: Project Setup

1. **Initialize project structure**
   ```bash
   mkdir -p app/{api/routes,core,ingestion,storage,ui/{templates,static}}
   mkdir -p tests/{unit,integration,fixtures}
   mkdir -p documents data plan scripts
   touch app/__init__.py app/api/__init__.py ...
   ```

2. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Configuration (`app/config.py`)**
   ```python
   from pydantic_settings import BaseSettings
   from pathlib import Path

   class Settings(BaseSettings):
       # API Keys
       anthropic_api_key: str

       # Paths
       database_url: str = "sqlite+aiosqlite:///./data/reasoning_rag.db"
       documents_path: Path = Path("./documents")

       # Reasoning
       max_reasoning_iterations: int = 8
       query_timeout_seconds: int = 60

       # Models
       reasoning_model: str = "claude-sonnet-4-6"
       annotation_model: str = "claude-haiku-4-5-20251001"

       # Logging
       log_level: str = "INFO"

       model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

   settings = Settings()
   ```

#### Day 3-4: Database Setup

1. **Database connection (`app/storage/database.py`)**
   ```python
   from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
   from sqlalchemy.orm import sessionmaker
   from app.config import settings
   from app.storage.models import Base

   engine = create_async_engine(settings.database_url, echo=False)
   AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

   async def init_db():
       async with engine.begin() as conn:
           await conn.run_sync(Base.metadata.create_all)

   async def get_db():
       async with AsyncSessionLocal() as session:
           yield session
   ```

2. **Repository pattern (`app/storage/repositories.py`)**
   - `DocumentRepository`: CRUD for documents
   - `ParagraphRepository`: CRUD for paragraphs, text search
   - `CrossReferenceRepository`: CRUD for cross-references
   - `CacheRepository`: Query cache operations

#### Day 5: FastAPI Skeleton

1. **Main app (`app/main.py`)**
   ```python
   from contextlib import asynccontextmanager
   from fastapi import FastAPI
   from app.storage.database import init_db
   from app.api.routes import query, documents

   @asynccontextmanager
   async def lifespan(app: FastAPI):
       await init_db()
       # Load ToC corpus into memory (L2 cache)
       yield
       # Cleanup

   app = FastAPI(
       title="Reasoning-RAG",
       description="Reasoning-driven document QA for Caritas Switzerland",
       version="0.1.0",
       lifespan=lifespan,
   )

   app.include_router(query.router, prefix="/api", tags=["Query"])
   app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
   ```

2. **Pydantic schemas (`app/api/schemas.py`)**
   ```python
   from pydantic import BaseModel
   from typing import Optional

   class QueryRequest(BaseModel):
       question: str
       doc_ids: Optional[list[str]] = None

   class Citation(BaseModel):
       para_id: str
       doc_title: str
       section: str
       page: int
       text_snippet: str
       original_url: str

   class QueryResponse(BaseModel):
       query_id: str
       answer: str
       confidence: str
       confidence_statement: str
       citations: list[Citation]
       gaps: Optional[str] = None
       sections_explored: list[str]
       iterations: int
       latency_breakdown: dict[str, int]
   ```

### Week 2: Ingestion Pipeline

#### Day 1-2: Docling Integration

1. **Docling parser (`app/ingestion/docling_parser.py`)**
   ```python
   from pathlib import Path
   from docling.document_converter import DocumentConverter
   from docling.datamodel.document import ConversionResult

   class DoclingParser:
       """Wrapper for Docling PDF/DOCX/PPTX → Markdown conversion."""

       def __init__(self):
           self.converter = DocumentConverter()

       async def parse(self, file_path: Path) -> tuple[str, dict]:
           """
           Parse document to Markdown with metadata.

           Returns:
               tuple: (markdown_content, metadata_dict)
           """
           result: ConversionResult = self.converter.convert(str(file_path))

           markdown = result.document.export_to_markdown()
           metadata = {
               "title": result.document.title or file_path.stem,
               "page_count": len(result.document.pages),
               "file_type": file_path.suffix[1:].lower(),
           }

           return markdown, metadata
   ```

2. **Format validation**
   ```python
   import magic

   ALLOWED_MIMES = {
       "application/pdf",
       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
       "application/vnd.openxmlformats-officedocument.presentationml.presentation",
   }

   def validate_file(file_path: Path) -> bool:
       mime = magic.from_file(str(file_path), mime=True)
       return mime in ALLOWED_MIMES
   ```

#### Day 3-4: Structure Analysis

1. **Markdown structure analysis (`app/ingestion/structure.py`)**
   ```python
   import re
   from dataclasses import dataclass

   @dataclass
   class Section:
       section_id: str
       title: str
       heading_level: int
       content: str
       page_start: int | None
       page_end: int | None
       parent_id: str | None
       children: list["Section"]

   class MarkdownStructureAnalyzer:
       """Parse Markdown heading hierarchy into section tree."""

       HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

       def analyze(self, markdown: str) -> list[Section]:
           """Extract hierarchical section structure from Markdown."""
           sections = []
           current_stack = []  # Track parent sections at each level
           section_counter = [0] * 6  # Counters for each heading level

           lines = markdown.split("\n")
           current_content = []
           current_section = None

           for line in lines:
               match = self.HEADING_PATTERN.match(line)
               if match:
                   # Save previous section content
                   if current_section:
                       current_section.content = "\n".join(current_content).strip()

                   level = len(match.group(1))
                   title = match.group(2).strip()

                   # Generate section ID
                   section_counter[level - 1] += 1
                   for i in range(level, 6):
                       section_counter[i] = 0

                   section_id = "s" + ".".join(
                       str(section_counter[i])
                       for i in range(level)
                       if section_counter[i] > 0
                   )

                   # Find parent
                   parent_id = None
                   if level > 1 and current_stack:
                       for parent in reversed(current_stack):
                           if parent.heading_level < level:
                               parent_id = parent.section_id
                               break

                   current_section = Section(
                       section_id=section_id,
                       title=title,
                       heading_level=level,
                       content="",
                       page_start=None,
                       page_end=None,
                       parent_id=parent_id,
                       children=[],
                   )

                   sections.append(current_section)

                   # Update stack
                   while current_stack and current_stack[-1].heading_level >= level:
                       current_stack.pop()
                   current_stack.append(current_section)

                   current_content = []
               else:
                   current_content.append(line)

           # Save last section content
           if current_section:
               current_section.content = "\n".join(current_content).strip()

           return sections
   ```

2. **Paragraph extraction**
   ```python
   import re
   from dataclasses import dataclass

   @dataclass
   class Paragraph:
       para_id: str
       text: str
       section_id: str
       para_index: int
       markdown_source: str

   class ParagraphExtractor:
       """Extract paragraphs from section content."""

       PARAGRAPH_SPLIT = re.compile(r"\n\n+")

       def extract(self, doc_id: str, sections: list[Section]) -> list[Paragraph]:
           paragraphs = []

           for section in sections:
               if not section.content.strip():
                   continue

               raw_paragraphs = self.PARAGRAPH_SPLIT.split(section.content)

               for idx, text in enumerate(raw_paragraphs, start=1):
                   text = text.strip()
                   if not text:
                       continue

                   para_id = f"{doc_id}:{section.section_id}:p{idx:03d}"

                   paragraphs.append(Paragraph(
                       para_id=para_id,
                       text=text,
                       section_id=section.section_id,
                       para_index=idx,
                       markdown_source=text,
                   ))

           return paragraphs
   ```

#### Day 5: Haiku Annotation

1. **Annotator (`app/ingestion/annotator.py`)**
   ```python
   from anthropic import Anthropic
   from app.config import settings

   class HaikuAnnotator:
       """Generate section summaries and detect language using Haiku."""

       def __init__(self):
           self.client = Anthropic(api_key=settings.anthropic_api_key)

       async def annotate_section(
           self,
           title: str,
           content: str,
           context: str = "",
       ) -> dict:
           """Generate summary and extract metadata for a section."""

           prompt = f"""Analyze this document section and provide:
   1. A concise summary (1-3 sentences based on complexity)
   2. The primary language (de, fr, it, or en)
   3. Key topics (3-5 keywords)
   4. Any cross-references to other sections/documents (e.g., "see Section X", "gemäss Anhang Y")

   Section Title: {title}

   Content:
   {content[:3000]}  # Truncate for token limits

   Respond in JSON format:
   {{
       "summary": "...",
       "language": "de|fr|it|en",
       "topics": ["topic1", "topic2"],
       "cross_references": ["see Section 3.2", "gemäss Anhang B"]
   }}"""

           response = self.client.messages.create(
               model=settings.annotation_model,
               max_tokens=500,
               messages=[{"role": "user", "content": prompt}]
           )

           # Parse JSON response
           import json
           return json.loads(response.content[0].text)
   ```

### Week 3: Reasoning Engine

#### Day 1-2: Tool Implementations

See [Section 7: Tool Implementations](#7-tool-implementations) for detailed code.

#### Day 3-4: Orchestrator

See [Section 8: Orchestrator Design](#8-orchestrator-design) for detailed code.

#### Day 5: SSE Streaming

1. **Progress streaming (`app/api/routes/query.py`)**
   ```python
   from fastapi import APIRouter, Depends
   from sse_starlette.sse import EventSourceResponse
   from app.core.orchestrator import ReasoningOrchestrator

   router = APIRouter()

   @router.post("/query")
   async def submit_query(request: QueryRequest, db: AsyncSession = Depends(get_db)):
       """Submit a query and get query_id for streaming."""
       query_id = str(uuid4())
       # Store query in processing queue
       return {"query_id": query_id, "status": "processing"}

   @router.get("/query/{query_id}/stream")
   async def stream_response(query_id: str, db: AsyncSession = Depends(get_db)):
       """Stream reasoning progress and final answer via SSE."""

       async def event_generator():
           orchestrator = ReasoningOrchestrator(db)

           async for event in orchestrator.run_with_progress(query_id):
               if event["type"] == "progress":
                   yield {
                       "event": "progress",
                       "data": json.dumps(event["data"])
                   }
               elif event["type"] == "answer":
                   yield {
                       "event": "answer",
                       "data": json.dumps(event["data"])
                   }
                   break

       return EventSourceResponse(event_generator())
   ```

### Week 4: Integration & Testing

#### Day 1-2: Integration Tests

1. **Mock Anthropic responses (`tests/fixtures/mock_responses.py`)**
   ```python
   MOCK_TOOL_CALLS = {
       "get_toc_response": {
           "doc_id": "test123",
           "title": "Test Policy",
           "nodes": [...]
       },
       "read_section_response": {
           "paragraphs": [
               {"para_id": "test123:s001:p001", "text": "..."}
           ]
       }
   }
   ```

2. **Integration test (`tests/integration/test_orchestrator.py`)**
   ```python
   import pytest
   from unittest.mock import AsyncMock, patch

   @pytest.mark.asyncio
   async def test_simple_factual_query(db_session):
       with patch("app.core.orchestrator.Anthropic") as mock_client:
           # Configure mock responses
           mock_client.return_value.messages.create = AsyncMock(
               return_value=MOCK_REASONING_RESPONSE
           )

           orchestrator = ReasoningOrchestrator(db_session)
           result = await orchestrator.run("What is the password policy?")

           assert result.confidence in ["high", "medium", "low"]
           assert len(result.citations) > 0
   ```

#### Day 3-4: 10 Test Questions

Create initial test suite with 10 question-answer pairs:

| # | Category | Question | Expected Source |
|---|----------|----------|-----------------|
| 1 | Factual | What is the password rotation policy? | Security Policy §4.2 |
| 2 | Factual | Who is responsible for data backups? | IT Operations §2.1 |
| 3 | Section | What does Section 3.2 say about access control? | Security Policy §3.2 |
| 4 | Synthesis | Summarize the incident response procedure | Security Policy §6 |
| 5 | Cross-ref | What are the requirements in Appendix A? | Appendix A |
| ... | ... | ... | ... |

#### Day 5: Documentation & Cleanup

- Complete docstrings for all modules
- Type hints verified with mypy
- README with setup instructions
- CLI script for testing queries

---

## 5. Phase 2: Multi-Document Reasoning

**Goal:** Cross-document reasoning, full tool set, web UI.

### Weeks 5-6: Multi-Document Support

1. **DOCX/PPTX support** - Already handled by Docling, verify parsing quality

2. **Cross-reference detection (`app/ingestion/cross_references.py`)**
   ```python
   import re

   REFERENCE_PATTERNS = [
       r"(?:see|siehe|voir|vedi)\s+(?:Section|Abschnitt|chapitre|sezione)\s+(\d+(?:\.\d+)*)",
       r"(?:gemäss|selon|secondo)\s+(?:Anhang|Annexe|Allegato)\s+([A-Z])",
       r"(?:refer to|verweist auf)\s+(.+?(?:Policy|Richtlinie|politique))",
   ]

   class CrossReferenceExtractor:
       def extract(self, text: str) -> list[dict]:
           references = []
           for pattern in REFERENCE_PATTERNS:
               for match in re.finditer(pattern, text, re.IGNORECASE):
                   references.append({
                       "source_text": match.group(0),
                       "target_hint": match.group(1),
                   })
           return references
   ```

3. **`list_documents` tool**
   ```python
   async def list_documents(
       topic: str | None = None,
       language: str | None = None,
   ) -> list[dict]:
       """List available documents with optional filtering."""
       query = select(Document)
       if language:
           query = query.where(Document.language == language)
       # Topic filtering via summary/title search
       ...
   ```

4. **`search_fallback` tool (embeddings)**
   ```python
   from sentence_transformers import SentenceTransformer
   import faiss

   class EmbeddingSearch:
       def __init__(self):
           self.model = SentenceTransformer(
               "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
           )
           self.index = None  # FAISS index loaded at startup

       async def search(
           self,
           query: str,
           doc_ids: list[str] | None = None,
           top_k: int = 10,
       ) -> list[dict]:
           query_embedding = self.model.encode(query)
           distances, indices = self.index.search(query_embedding, top_k)
           # Map indices back to para_ids
           ...
   ```

### Weeks 7-8: Web UI

1. **Base template (`app/ui/templates/base.html`)**
   ```html
   <!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>{% block title %}Reasoning-RAG{% endblock %}</title>
       <script src="/static/js/htmx.min.js"></script>
       <link rel="stylesheet" href="/static/css/styles.css">
   </head>
   <body>
       <main>{% block content %}{% endblock %}</main>
   </body>
   </html>
   ```

2. **Query interface with htmx**
   ```html
   <form hx-post="/api/query" hx-target="#results" hx-swap="innerHTML">
       <input type="text" name="question" placeholder="Ask a question...">
       <button type="submit">Ask</button>
   </form>

   <div id="progress" hx-ext="sse" sse-connect="/api/query/{id}/stream">
       <div sse-swap="progress"></div>
   </div>

   <div id="results"></div>
   ```

3. **Citation side panel**
   ```html
   <div id="citation-panel" class="side-panel">
       <button onclick="closePanel()">×</button>
       <div id="citation-content">
           <!-- Loaded via htmx on citation click -->
       </div>
   </div>
   ```

---

## 6. Phase 3: Production System

**Goal:** Full caching, monitoring, admin panel, evaluation suite.

### Caching (L1-L5)

See [Section 10: Caching Implementation](#10-caching-implementation).

### Admin Panel

1. **Document management**
   - Upload with format validation
   - Delete with cascade invalidation
   - View ingestion status and unresolved cross-references

2. **Monitoring dashboard**
   - Cache hit rates (L1-L5)
   - Query latency breakdown
   - Rate limit warnings

3. **Debug tools**
   - Dry-run mode (cached results only)
   - Reasoning trace viewer (chat-like format)

### Evaluation Suite

1. **50 test cases** across categories:
   - 15 factual lookup (single doc)
   - 10 factual lookup (specific section)
   - 8 synthesis (single doc)
   - 7 synthesis (cross-doc)
   - 5 cross-reference following
   - 5 unanswerable

2. **Automated pipeline**
   ```python
   async def run_evaluation():
       results = []
       for test_case in TEST_CASES:
           result = await orchestrator.run(test_case.question)

           # Compare with gold standard
           correctness = evaluate_correctness(result.answer, test_case.expected)
           citation_accuracy = verify_citations(result.citations)

           results.append({
               "test_id": test_case.id,
               "correctness": correctness,
               "citation_accuracy": citation_accuracy,
               "iterations": result.iterations,
               "latency_ms": result.latency,
           })

       # Persist results for trend analysis
       await save_evaluation_run(results)
   ```

---

## 7. Tool Implementations

### Tool Schema for Anthropic API

```python
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
                "doc_id": {"type": "string"},
                "node_id": {"type": "string", "description": "Section node ID (e.g., 's001.1')"}
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
                "query_text": {"type": "string", "description": "Text or regex pattern to search"},
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
                    "default": 10
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
                "query_text": {"type": "string"},
                "doc_ids": {"type": "array", "items": {"type": "string"}},
                "top_k": {"type": "integer", "default": 10}
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
                "para_id": {"type": "string"},
                "relevance_note": {"type": "string", "description": "Why this paragraph is relevant"}
            },
            "required": ["para_id", "relevance_note"]
        }
    }
]
```

### Tool Handler (`app/core/tools.py`)

```python
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.repositories import DocumentRepository, ParagraphRepository

class ToolHandler:
    """Execute tool calls from the orchestrator."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.para_repo = ParagraphRepository(db)
        self.evidence_log: list[dict] = []
        self.visited_sections: set[str] = set()

    async def execute(self, tool_name: str, tool_input: dict) -> Any:
        """Route tool call to appropriate handler."""
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

        return await handler(**tool_input)

    async def _list_documents(
        self,
        topic: str | None = None,
        language: str | None = None
    ) -> list[dict]:
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
        doc = await self.doc_repo.get_by_id(doc_id)
        if not doc:
            return {"error": f"Document {doc_id} not found"}
        return doc.toc_json

    async def _read_section(self, doc_id: str, node_id: str) -> dict:
        section_key = f"{doc_id}:{node_id}"
        self.visited_sections.add(section_key)

        paragraphs = await self.para_repo.get_by_section(doc_id, node_id)
        return {
            "section": node_id,
            "paragraphs": [
                {
                    "para_id": p.para_id,
                    "text": p.text,
                    "page": p.page_number,
                }
                for p in paragraphs
            ]
        }

    async def _read_paragraphs(self, para_ids: list[str]) -> list[dict]:
        paragraphs = await self.para_repo.get_by_ids(para_ids)
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
    ) -> list[dict]:
        try:
            results = await self.para_repo.search_text(
                query_text,
                doc_ids=doc_ids,
                regex=regex,
                limit=max_results,
            )

            # Add context paragraphs
            if context_paragraphs > 0:
                results = await self._add_context(results, context_paragraphs)

            return results
        except Exception as e:
            # Handle regex errors gracefully
            return {"error": f"Search failed: {str(e)}"}

    async def _search_fallback(
        self,
        query_text: str,
        doc_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        # Phase 2 implementation
        raise NotImplementedError("search_fallback available in Phase 2")

    async def _record_evidence(self, para_id: str, relevance_note: str) -> dict:
        self.evidence_log.append({
            "para_id": para_id,
            "relevance": relevance_note,
            "iteration": len(self.evidence_log) + 1,
        })
        return {"recorded": True, "evidence_count": len(self.evidence_log)}
```

---

## 8. Orchestrator Design

### System Prompt (`app/core/prompts.py`)

```python
SYSTEM_PROMPT = """<role>
You are a document research assistant for Caritas Switzerland.
You answer questions about internal policy, regulation, and research documents.
</role>

<reasoning_protocol>
Follow this process for every query:
1. If the query is ambiguous, ask the user to clarify before proceeding
2. Review the pre-loaded Table of Contents for all documents
3. Identify which documents and sections are likely relevant
4. Read the most promising section using read_section
5. If you encounter a cross-reference, use grep_documents to find and follow it
6. Evaluate whether you have sufficient evidence
7. If insufficient, read additional sections
8. When sufficient (or after 8 iterations), synthesize your answer
9. If evidence is incomplete, state what you found, what gaps remain, and suggest refinements
</reasoning_protocol>

<citation_rules>
- Every factual claim must cite a specific paragraph: [Document Title, Section X.Y, p.N]
- Page numbers are PDF physical page numbers
- Only cite paragraphs you have actually read via tool calls
- Never invent section numbers or page numbers
- For direct quotes, use the exact text from the paragraph
</citation_rules>

<cross_reference_rules>
- When you encounter text like "see Section X", "gemäss Anhang Y",
  "refer to [document name]", use grep_documents to locate the referenced content
- Follow cross-references across documents when they are relevant to the query
- If a cross-reference cannot be resolved, include inline warning in your answer:
  "Note: Referenced document/section not found"
- Track cross-referenced evidence separately in your evidence log
</cross_reference_rules>

<gap_reporting>
When evidence is insufficient, produce a structured response:
- What you DID find (with citations)
- What specific gaps remain
- Which sections and documents you searched
- Suggestions for how to refine the question
</gap_reporting>

<language>
Respond in the language of the user's question.
Documents may be in DE, FR, IT, or EN — handle all transparently.
When citing content in a different language than the response, preserve the source
language with an inline translation.
</language>

<out_of_scope>
If a question is clearly unrelated to Caritas documents (e.g., "What's the weather?"),
politely explain that you can only answer questions about internal documents and
suggest rephrasing the question.
</out_of_scope>

<pre_loaded_tocs>
{toc_corpus}
</pre_loaded_tocs>"""
```

### Orchestrator Implementation (`app/core/orchestrator.py`)

```python
from anthropic import Anthropic
from typing import AsyncIterator
from app.config import settings
from app.core.tools import ToolHandler, TOOLS
from app.core.prompts import SYSTEM_PROMPT
from app.core.evidence import EvidenceVerifier

class ReasoningOrchestrator:
    """Main reasoning loop orchestrator using Claude Sonnet."""

    def __init__(self, db):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.tool_handler = ToolHandler(db)
        self.evidence_verifier = EvidenceVerifier()
        self.max_iterations = settings.max_reasoning_iterations

    async def run_with_progress(
        self,
        query_id: str,
        question: str,
        doc_ids: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        """Run reasoning loop with progress updates via SSE."""

        # Load ToC corpus
        toc_corpus = await self._load_toc_corpus(doc_ids)
        system_prompt = SYSTEM_PROMPT.format(toc_corpus=toc_corpus)

        messages = [{"role": "user", "content": question}]
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # Call Claude with tools
            response = self.client.messages.create(
                model=settings.reasoning_model,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            # Process response
            assistant_content = []

            for block in response.content:
                if block.type == "text":
                    # Check if this is the final answer
                    if response.stop_reason == "end_turn":
                        # Verify citations
                        verified_answer = await self._verify_and_finalize(
                            block.text,
                            self.tool_handler.evidence_log,
                        )

                        yield {
                            "type": "answer",
                            "data": verified_answer,
                        }
                        return

                    assistant_content.append(block)

                elif block.type == "tool_use":
                    # Emit progress
                    yield {
                        "type": "progress",
                        "data": {
                            "iteration": iteration,
                            "tool": block.name,
                            "status": f"Calling {block.name}...",
                        }
                    }

                    # Execute tool
                    result = await self.tool_handler.execute(
                        block.name,
                        block.input
                    )

                    assistant_content.append(block)

                    # Add tool result to messages
                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }]
                    })
                    assistant_content = []

        # Max iterations reached
        yield {
            "type": "answer",
            "data": await self._synthesize_partial_answer(),
        }

    async def _verify_and_finalize(
        self,
        answer: str,
        evidence_log: list[dict]
    ) -> dict:
        """Verify citations and finalize answer."""

        # Extract citations from answer
        citations = self.evidence_verifier.extract_citations(answer)

        # Verify each citation exists in evidence log
        verified, unverified = self.evidence_verifier.verify(
            citations,
            evidence_log
        )

        if unverified:
            # Regenerate answer with stricter instructions
            answer = await self._regenerate_with_strict_citations(
                answer,
                evidence_log
            )
            citations = self.evidence_verifier.extract_citations(answer)

        # Determine confidence
        confidence = self._calculate_confidence(evidence_log, citations)

        return {
            "answer": answer,
            "confidence": confidence["level"],
            "confidence_statement": confidence["statement"],
            "citations": citations,
            "evidence_log": evidence_log,
            "sections_explored": list(self.tool_handler.visited_sections),
            "iterations": len(evidence_log),
        }

    def _calculate_confidence(
        self,
        evidence_log: list[dict],
        citations: list[dict],
    ) -> dict:
        """Calculate confidence level based on evidence quality."""

        if len(evidence_log) >= 3 and len(citations) >= 2:
            return {
                "level": "high",
                "statement": "Confidence: High - direct evidence from multiple sources"
            }
        elif len(evidence_log) >= 1:
            return {
                "level": "medium",
                "statement": "Confidence: Medium - some inference required"
            }
        else:
            return {
                "level": "low",
                "statement": "Confidence: Low - limited evidence, please verify independently"
            }
```

---

## 9. Ingestion Pipeline

### Pipeline Coordinator (`app/ingestion/pipeline.py`)

```python
from pathlib import Path
from uuid import uuid4
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.docling_parser import DoclingParser
from app.ingestion.structure import MarkdownStructureAnalyzer, ParagraphExtractor
from app.ingestion.annotator import HaikuAnnotator
from app.ingestion.cross_references import CrossReferenceExtractor
from app.ingestion.checkpoints import CheckpointManager
from app.storage.repositories import DocumentRepository

class IngestionPipeline:
    """Coordinate document ingestion with checkpoint recovery."""

    STAGES = ["parsing", "structure", "paragraphs", "annotation", "cross_refs", "indexing"]

    def __init__(self, db: AsyncSession):
        self.db = db
        self.parser = DoclingParser()
        self.structure_analyzer = MarkdownStructureAnalyzer()
        self.paragraph_extractor = ParagraphExtractor()
        self.annotator = HaikuAnnotator()
        self.xref_extractor = CrossReferenceExtractor()
        self.checkpoint_mgr = CheckpointManager(db)
        self.doc_repo = DocumentRepository(db)

    async def ingest(
        self,
        file_path: Path,
        doc_id: str | None = None
    ) -> str:
        """
        Ingest a document with checkpoint recovery.

        Returns:
            str: The document ID
        """
        # Generate doc_id if not resuming
        if not doc_id:
            doc_id = str(uuid4())[:12]

        # Check for existing checkpoint
        checkpoint = await self.checkpoint_mgr.get(doc_id)
        start_stage = checkpoint.stage if checkpoint else "parsing"

        try:
            # Stage 1: Parsing
            if self._should_run_stage("parsing", start_stage):
                markdown, metadata = await self.parser.parse(file_path)
                await self.checkpoint_mgr.save(doc_id, "parsing", {
                    "markdown": markdown,
                    "metadata": metadata,
                })
            else:
                data = checkpoint.stage_data
                markdown, metadata = data["markdown"], data["metadata"]

            # Stage 2: Structure analysis
            if self._should_run_stage("structure", start_stage):
                sections = self.structure_analyzer.analyze(markdown)
                await self.checkpoint_mgr.save(doc_id, "structure", {
                    "sections": [s.__dict__ for s in sections],
                    "markdown": markdown,
                    "metadata": metadata,
                })
            else:
                sections = [Section(**s) for s in checkpoint.stage_data["sections"]]

            # Stage 3: Paragraph extraction
            if self._should_run_stage("paragraphs", start_stage):
                paragraphs = self.paragraph_extractor.extract(doc_id, sections)
                await self.checkpoint_mgr.save(doc_id, "paragraphs", {
                    "paragraphs": [p.__dict__ for p in paragraphs],
                    "sections": [s.__dict__ for s in sections],
                    "metadata": metadata,
                })
            else:
                paragraphs = [Paragraph(**p) for p in checkpoint.stage_data["paragraphs"]]

            # Stage 4: Annotation (Haiku)
            if self._should_run_stage("annotation", start_stage):
                annotated_sections = []
                for section in sections:
                    annotation = await self.annotator.annotate_section(
                        section.title,
                        section.content
                    )
                    section.summary = annotation["summary"]
                    annotated_sections.append(section)

                await self.checkpoint_mgr.save(doc_id, "annotation", {
                    "sections": [s.__dict__ for s in annotated_sections],
                    "paragraphs": [p.__dict__ for p in paragraphs],
                    "metadata": metadata,
                    "language": annotation.get("language", "de"),
                })

            # Stage 5: Cross-reference extraction
            if self._should_run_stage("cross_refs", start_stage):
                cross_refs = []
                for para in paragraphs:
                    refs = self.xref_extractor.extract(para.text)
                    for ref in refs:
                        cross_refs.append({
                            "source_para_id": para.para_id,
                            **ref,
                        })

                await self.checkpoint_mgr.save(doc_id, "cross_refs", {
                    "cross_refs": cross_refs,
                    "sections": checkpoint.stage_data["sections"],
                    "paragraphs": checkpoint.stage_data["paragraphs"],
                    "metadata": checkpoint.stage_data["metadata"],
                    "language": checkpoint.stage_data["language"],
                })

            # Stage 6: Store in database
            if self._should_run_stage("indexing", start_stage):
                await self._store_document(
                    doc_id=doc_id,
                    file_path=file_path,
                    sections=annotated_sections,
                    paragraphs=paragraphs,
                    cross_refs=cross_refs,
                    metadata=metadata,
                    language=checkpoint.stage_data["language"],
                )

                # Clear checkpoint on success
                await self.checkpoint_mgr.delete(doc_id)

            return doc_id

        except Exception as e:
            # Checkpoint already saved at last successful stage
            raise IngestionError(f"Ingestion failed at {start_stage}: {e}")

    def _should_run_stage(self, stage: str, start_stage: str) -> bool:
        """Determine if a stage should run based on checkpoint."""
        return self.STAGES.index(stage) >= self.STAGES.index(start_stage)

    async def _store_document(self, **kwargs):
        """Store document, sections, paragraphs, and cross-refs in DB."""
        # Build ToC JSON from sections
        toc_json = self._build_toc_json(kwargs["sections"])

        # Create document record
        await self.doc_repo.create(
            doc_id=kwargs["doc_id"],
            title=kwargs["metadata"]["title"],
            file_type=kwargs["metadata"]["file_type"],
            language=kwargs["language"],
            total_pages=kwargs["metadata"]["page_count"],
            file_hash=self._compute_hash(kwargs["file_path"]),
            toc_json=toc_json,
        )

        # Store sections, paragraphs, cross_refs
        # ...
```

---

## 10. Caching Implementation

### Cache Manager (`app/storage/cache.py`)

```python
from datetime import datetime
from typing import Any
import json
import hashlib

class CacheManager:
    """Unified cache manager for L1-L5 cache layers."""

    def __init__(self, db):
        self.db = db
        self._toc_corpus_cache: dict | None = None  # L2: In-memory

    # L1: Ingestion Cache (filesystem-based)
    async def get_ingestion_cache(self, file_hash: str) -> dict | None:
        """Check if document was already processed."""
        doc = await self.db.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return doc.first()

    # L2: ToC Corpus Cache (in-memory)
    async def get_toc_corpus(self) -> dict:
        """Get combined ToC for all documents."""
        if self._toc_corpus_cache is None:
            docs = await self.db.execute(select(Document))
            self._toc_corpus_cache = {
                doc.doc_id: doc.toc_json
                for doc in docs.scalars()
            }
        return self._toc_corpus_cache

    def invalidate_toc_corpus(self):
        """Invalidate L2 cache when any document changes."""
        self._toc_corpus_cache = None

    # L4: Query Result Cache
    async def get_query_result(
        self,
        query: str,
        doc_scope: list[str] | None = None
    ) -> dict | None:
        """Check for cached query result."""
        query_hash = self._compute_query_hash(query, doc_scope)

        result = await self.db.execute(
            select(QueryCache).where(QueryCache.query_hash == query_hash)
        )
        cached = result.first()

        if cached:
            return {
                "answer": cached.answer,
                "confidence": cached.confidence,
                "citations": cached.citations,
                "cache_hit": True,
            }
        return None

    async def cache_query_result(
        self,
        query: str,
        doc_scope: list[str] | None,
        result: dict,
    ):
        """Store query result in cache."""
        query_hash = self._compute_query_hash(query, doc_scope)

        cache_entry = QueryCache(
            query_hash=query_hash,
            query_text=query,
            doc_scope=doc_scope,
            answer=result["answer"],
            confidence=result["confidence"],
            citations=result["citations"],
            evidence_log=result.get("evidence_log"),
            sections_explored=result.get("sections_explored"),
            iterations=result.get("iterations"),
        )

        self.db.add(cache_entry)
        await self.db.commit()

    async def invalidate_for_document(self, doc_id: str):
        """Invalidate all caches related to a document."""
        # L2: ToC corpus
        self.invalidate_toc_corpus()

        # L4: Query results citing this document
        await self.db.execute(
            delete(QueryCache).where(
                QueryCache.citations.contains(doc_id)
            )
        )

        await self.db.commit()

    # L5: Reasoning Trace (no TTL, forever retention)
    async def store_reasoning_trace(
        self,
        query_id: str,
        query_text: str,
        trace: list[dict],
        answer: str,
        latency_ms: int,
    ):
        """Store full reasoning trace for audit."""
        trace_entry = ReasoningTrace(
            query_id=query_id,
            query_text=query_text,
            trace_json=trace,
            answer=answer,
            latency_ms=latency_ms,
            iterations=len([t for t in trace if t.get("type") == "tool_call"]),
        )

        self.db.add(trace_entry)
        await self.db.commit()

    def _compute_query_hash(
        self,
        query: str,
        doc_scope: list[str] | None
    ) -> str:
        """Compute cache key for a query."""
        key = query + (json.dumps(sorted(doc_scope)) if doc_scope else "")
        return hashlib.sha256(key.encode()).hexdigest()
```

---

## 11. API Endpoints

### Query Routes (`app/api/routes/query.py`)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse
from uuid import uuid4
import json
import time

from app.api.schemas import QueryRequest, QueryResponse
from app.storage.database import get_db
from app.storage.cache import CacheManager
from app.core.orchestrator import ReasoningOrchestrator

router = APIRouter()

@router.post("/query", response_model=dict)
async def submit_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a question for processing.

    Returns query_id for streaming results.
    """
    query_id = str(uuid4())

    # Check cache first
    cache = CacheManager(db)
    cached = await cache.get_query_result(request.question, request.doc_ids)

    if cached:
        # Log cache hit
        await log_query(db, query_id, request.question, cache_hit=True)
        return {
            "query_id": query_id,
            "status": "cached",
            **cached,
        }

    # Store query for processing
    # (In production, use a proper task queue)

    return {
        "query_id": query_id,
        "status": "processing",
        "stream_url": f"/api/query/{query_id}/stream",
    }

@router.get("/query/{query_id}/stream")
async def stream_query_response(
    query_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream reasoning progress and final answer via SSE.

    Events:
    - progress: Intermediate status updates
    - answer: Final answer with citations
    - error: If something goes wrong
    """
    async def event_generator():
        start_time = time.time()

        try:
            # Get query from storage (simplified - use proper queue in production)
            query_text = await get_pending_query(db, query_id)

            orchestrator = ReasoningOrchestrator(db)
            cache = CacheManager(db)

            async for event in orchestrator.run_with_progress(query_id, query_text):
                if event["type"] == "progress":
                    yield {
                        "event": "progress",
                        "data": json.dumps(event["data"]),
                    }

                elif event["type"] == "answer":
                    result = event["data"]

                    # Cache result
                    await cache.cache_query_result(
                        query_text,
                        None,  # doc_scope
                        result
                    )

                    # Store reasoning trace (L5 - forever)
                    latency_ms = int((time.time() - start_time) * 1000)
                    await cache.store_reasoning_trace(
                        query_id,
                        query_text,
                        result.get("evidence_log", []),
                        result["answer"],
                        latency_ms,
                    )

                    # Log query
                    await log_query(
                        db,
                        query_id,
                        query_text,
                        cache_hit=False,
                        latency_ms=latency_ms,
                        iterations=result.get("iterations"),
                        confidence=result.get("confidence"),
                    )

                    yield {
                        "event": "answer",
                        "data": json.dumps({
                            "answer": result["answer"],
                            "confidence": result["confidence"],
                            "confidence_statement": result["confidence_statement"],
                            "citations": result["citations"],
                            "sections_explored": result["sections_explored"],
                            "iterations": result["iterations"],
                            "latency_breakdown": {
                                "total_ms": latency_ms,
                            },
                        }),
                    }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())

@router.post("/query/{query_id}/feedback")
async def submit_feedback(
    query_id: str,
    rating: str,
    category: str | None = None,
    details: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback on a query result."""
    feedback = UserFeedback(
        query_id=query_id,
        rating=rating,
        category=category,
        details=details,
    )
    db.add(feedback)
    await db.commit()

    return {"status": "recorded"}
```

### Document Routes (`app/api/routes/documents.py`)

```python
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import aiofiles
import shutil

from app.storage.database import get_db
from app.storage.cache import CacheManager
from app.ingestion.pipeline import IngestionPipeline
from app.config import settings

router = APIRouter()

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and ingest a document.

    Supported formats: PDF, DOCX, PPTX
    """
    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".pptx"}
    ext = Path(file.filename).suffix.lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}"
        )

    # Generate doc_id and save file
    doc_id = str(uuid4())[:12]
    doc_dir = settings.documents_path / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    file_path = doc_dir / f"original{ext}"

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Start ingestion (async)
    pipeline = IngestionPipeline(db)

    try:
        await pipeline.ingest(file_path, doc_id)

        return {
            "doc_id": doc_id,
            "status": "ingested",
            "filename": file.filename,
        }

    except Exception as e:
        # Clean up on failure
        shutil.rmtree(doc_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a document and invalidate all related caches.
    """
    # Delete from database (cascades to sections, paragraphs, cross_refs)
    result = await db.execute(
        delete(Document).where(Document.doc_id == doc_id)
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Document not found")

    # Invalidate caches
    cache = CacheManager(db)
    await cache.invalidate_for_document(doc_id)

    # Delete files
    doc_dir = settings.documents_path / doc_id
    shutil.rmtree(doc_dir, ignore_errors=True)

    await db.commit()

    return {"status": "deleted", "doc_id": doc_id}

@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
):
    """List all ingested documents."""
    result = await db.execute(select(Document))
    docs = result.scalars().all()

    return [
        {
            "doc_id": d.doc_id,
            "title": d.title,
            "language": d.language,
            "total_pages": d.total_pages,
            "file_type": d.file_type,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]

@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get document details including ToC."""
    result = await db.execute(
        select(Document).where(Document.doc_id == doc_id)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "doc_id": doc.doc_id,
        "title": doc.title,
        "summary": doc.summary,
        "language": doc.language,
        "total_pages": doc.total_pages,
        "file_type": doc.file_type,
        "toc": doc.toc_json,
        "created_at": doc.created_at.isoformat(),
    }
```

---

## 12. Testing Strategy

### Unit Tests

```
tests/unit/
├── test_tools.py           # Test each tool handler
├── test_structure.py       # Test Markdown parsing
├── test_annotator.py       # Test Haiku annotation (mocked)
├── test_evidence.py        # Test citation verification
├── test_cache.py           # Test cache operations
└── test_cross_refs.py      # Test cross-reference extraction
```

### Integration Tests

```
tests/integration/
├── test_ingestion.py       # Full ingestion pipeline
├── test_orchestrator.py    # Reasoning loop with mocked API
├── test_api.py             # FastAPI endpoint tests
└── test_sse.py             # SSE streaming tests
```

### Test Fixtures

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.storage.models import Base

@pytest.fixture
async def db_session():
    """Create in-memory SQLite database for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
def mock_anthropic_client(mocker):
    """Mock Anthropic API client."""
    mock = mocker.patch("app.core.orchestrator.Anthropic")
    return mock

@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return {
        "doc_id": "test123",
        "title": "Test Policy",
        "markdown": "# 1. Introduction\n\nThis is a test...",
    }
```

### Mock API Responses

```python
# tests/fixtures/mock_responses.py
MOCK_TOOL_USE_RESPONSE = {
    "id": "msg_123",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "tool_use",
            "id": "tool_123",
            "name": "read_section",
            "input": {"doc_id": "test123", "node_id": "s001"}
        }
    ],
    "stop_reason": "tool_use",
}

MOCK_FINAL_ANSWER = {
    "id": "msg_456",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "text",
            "text": "Based on the ICT Security Policy [Section 4.2, p.5], passwords must be rotated every 90 days."
        }
    ],
    "stop_reason": "end_turn",
}
```

---

## 13. Development Guidelines

### Code Style

- **Type hints**: Required for all function signatures
- **Docstrings**: Google style for all public functions
- **Line length**: 100 characters max
- **Formatting**: Ruff (auto-format on save)
- **Import order**: stdlib → third-party → local

### Commit Convention

```
feat: Add grep_documents tool with regex support
fix: Handle empty section content in parser
docs: Update PLAN.md with Phase 2 details
test: Add integration tests for ingestion pipeline
refactor: Extract citation verification to separate module
```

### PR Checklist

- [ ] Tests pass (`pytest`)
- [ ] Type check passes (`mypy app/`)
- [ ] Linting passes (`ruff check app/`)
- [ ] Docstrings for new public functions
- [ ] PLAN.md updated if architecture changes

### Development Workflow

1. **Start server**: `uvicorn app.main:app --reload`
2. **Run tests**: `pytest -v`
3. **Type check**: `mypy app/`
4. **Lint**: `ruff check app/`
5. **Format**: `ruff format app/`

### Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# Initialize database
python scripts/init_db.py

# Run development server
uvicorn app.main:app --reload
```

---

## Appendix: Quick Reference

### File Locations

| Purpose | Path |
|---------|------|
| FastAPI entry | `app/main.py` |
| Configuration | `app/config.py` |
| Tool handlers | `app/core/tools.py` |
| Orchestrator | `app/core/orchestrator.py` |
| System prompt | `app/core/prompts.py` |
| DB models | `app/storage/models.py` |
| Ingestion | `app/ingestion/pipeline.py` |
| API routes | `app/api/routes/` |

### Key Constants

| Constant | Value | Location |
|----------|-------|----------|
| Max iterations | 8 | `app/config.py` |
| Query timeout | 60s | `app/config.py` |
| Reasoning model | claude-sonnet-4-6 | `app/config.py` |
| Annotation model | claude-haiku-4-5-20251001 | `app/config.py` |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/query` | Submit query |
| GET | `/api/query/{id}/stream` | SSE stream |
| POST | `/api/documents/upload` | Upload document |
| GET | `/api/documents` | List documents |
| DELETE | `/api/documents/{id}` | Delete document |
