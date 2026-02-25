# TASKS.md — Parallel Agent Implementation Guide

**Version:** 1.0
**Date:** 2026-02-22
**Reference:** `plan/plan.md` (Implementation Plan v1.0)

---

## Overview

This document organizes implementation tasks for **6+ parallel agents** working simultaneously on the Reasoning-RAG system. Tasks are structured in dependency levels to maximize parallelism while ensuring correct build order.

### Phase Legend

- `[P1]` — Phase 1: MVP (Weeks 1-4) — Single-document factual QA
- `[P2]` — Phase 2: Multi-Document (Weeks 5-8) — Cross-document reasoning, web UI
- `[P3]` — Phase 3: Production (Weeks 9-12) — Caching, monitoring, evaluation suite

### Task Status Legend

- `[ ]` — Not started
- `[~]` — In progress
- `[x]` — Completed

---

## Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LEVEL 0: FOUNDATION                               │
│  (Must complete first - single agent, quick setup)                       │
│  • L0-001: Project structure scaffolding                                 │
│  • L0-002: pyproject.toml & .env setup                                   │
│  • L0-003: __init__.py files for all packages                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   LEVEL 1: INDEPENDENT MODULES                           │
│  (6 agents can work in parallel - no cross-dependencies)                 │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   STORAGE    │  │  INGESTION   │  │    CORE      │                   │
│  │   Agent 1    │  │   Agent 2    │  │   Agent 3    │                   │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤                   │
│  │ L1-S-001-007 │  │ L1-I-001-008 │  │ L1-C-001-006 │                   │
│  │ models.py    │  │ docling.py   │  │ prompts.py   │                   │
│  │ database.py  │  │ structure.py │  │ evidence.py  │                   │
│  │ repos.py     │  │ annotator.py │  │ tool schemas │                   │
│  │ cache.py     │  │ checkpoints  │  │              │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │     API      │  │    TESTS     │  │   SCRIPTS    │                   │
│  │   Agent 4    │  │   Agent 5    │  │   Agent 6    │                   │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤                   │
│  │ L1-A-001-006 │  │ L1-T-001-006 │  │ L1-X-001-005 │                   │
│  │ schemas.py   │  │ conftest.py  │  │ init_db.py   │                   │
│  │ routes/      │  │ fixtures/    │  │ .gitignore   │                   │
│  │ dependencies │  │ mock data    │  │ README.md    │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   LEVEL 2: INTEGRATION TASKS                             │
│  (Require Level 1 modules - 4 agents)                                    │
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────────┐                     │
│  │   ORCHESTRATOR       │  │   INGESTION PIPELINE │                     │
│  │   (Core + Storage)   │  │   (Ingestion+Storage)│                     │
│  │   L2-O-001-004       │  │   L2-P-001-003       │                     │
│  └──────────────────────┘  └──────────────────────┘                     │
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────────┐                     │
│  │   FASTAPI APP        │  │   WEB UI             │                     │
│  │   (API + Core)       │  │   (Templates + htmx) │                     │
│  │   L2-F-001-005       │  │   L2-U-001-004       │                     │
│  └──────────────────────┘  └──────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   LEVEL 3: INTEGRATION TESTS & POLISH                    │
│  (Require Level 2 - 3 agents)                                            │
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────────┐                     │
│  │   INTEGRATION TESTS  │  │   EVALUATION SUITE   │                     │
│  │   L3-T-001-005       │  │   L3-E-001-004       │                     │
│  └──────────────────────┘  └──────────────────────┘                     │
│                                                                          │
│  ┌──────────────────────┐                                                │
│  │   ADMIN PANEL        │                                                │
│  │   L3-A-001-005       │                                                │
│  └──────────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Level 0: Foundation

**Estimated Time:** 1-2 hours
**Required Before:** All other tasks
**Agent Count:** 1 (sequential setup)

### L0-001: Create Directory Structure [P1]

**Stream**: Foundation
**Files**: All directories and `__init__.py` files
**Dependencies**: None
**Interfaces**: Project skeleton for all agents

**Acceptance Criteria**:
- [ ] Create `app/` with subdirectories: `api/routes/`, `core/`, `ingestion/`, `storage/`, `ui/templates/`, `ui/static/css/`, `ui/static/js/`
- [ ] Create `tests/` with subdirectories: `unit/`, `integration/`, `fixtures/sample_documents/`, `fixtures/mock_responses/`
- [ ] Create `documents/`, `data/`, `plan/`, `scripts/` directories
- [ ] Add empty `__init__.py` to all Python packages
- [ ] Verify structure matches `plan/plan.md` Section 1

```bash
# Commands to execute
mkdir -p app/{api/routes,core,ingestion,storage,ui/{templates/admin,static/{css,js}}}
mkdir -p tests/{unit,integration,fixtures/{sample_documents,mock_responses}}
mkdir -p documents data plan scripts
touch app/__init__.py app/api/__init__.py app/api/routes/__init__.py
touch app/core/__init__.py app/ingestion/__init__.py app/storage/__init__.py
touch app/ui/__init__.py tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
```

---

### L0-002: Create pyproject.toml [P1]

**Stream**: Foundation
**Files**: `pyproject.toml`
**Dependencies**: L0-001
**Interfaces**: Dependency manifest for all agents

**Acceptance Criteria**:
- [ ] Project name: `reasoning-rag`
- [ ] Python version: `>=3.12`
- [ ] Core dependencies: fastapi, uvicorn, anthropic, docling, sqlalchemy, aiosqlite, pydantic-settings, sse-starlette, jinja2, python-dateutil, aiofiles, python-multipart
- [ ] Dev dependencies: pytest, pytest-asyncio, pytest-cov, httpx, ruff, mypy
- [ ] Optional embeddings group: sentence-transformers, faiss-cpu
- [ ] Ruff config: line-length=100, target-version="py312"
- [ ] Pytest config: asyncio_mode="auto", testpaths=["tests"]
- [ ] Mypy config: python_version="3.12", strict=true
- [ ] Verify with `pip install -e ".[dev]"`

---

### L0-003: Create Environment Configuration [P1]

**Stream**: Foundation
**Files**: `.env.example`, `app/config.py`
**Dependencies**: L0-001, L0-002
**Interfaces**: `settings` object with all config values

**Acceptance Criteria**:
- [ ] Create `.env.example` with documented variables:
  - `ANTHROPIC_API_KEY` (required)
  - `DATABASE_URL` (default: `sqlite+aiosqlite:///./data/reasoning_rag.db`)
  - `DOCUMENTS_PATH` (default: `./documents`)
  - `MAX_REASONING_ITERATIONS` (default: 8)
  - `QUERY_TIMEOUT_SECONDS` (default: 60)
  - `LOG_LEVEL` (default: INFO)
- [ ] Create `app/config.py` with Pydantic Settings class
- [ ] Include model names: `reasoning_model`, `annotation_model`
- [ ] Export `settings = Settings()` singleton
- [ ] Add `.env` to `.gitignore`

---

## Level 1: Independent Modules

**Estimated Time:** 3-5 days per stream
**Required Before:** Level 2 integration
**Agent Count:** 6 (parallel work)

---

## Stream: STORAGE (Agent 1)

### L1-S-001: SQLAlchemy Models — Core Tables [P1]

**Stream**: Storage
**Files**: `app/storage/models.py`
**Dependencies**: L0-003
**Interfaces**: `Base`, `Document`, `Section`, `Paragraph` classes

**Acceptance Criteria**:
- [ ] Create `Base` declarative base class
- [ ] Create `Document` model with fields: `doc_id` (PK, String(12)), `title`, `file_type`, `language`, `total_pages`, `file_hash` (indexed), `toc_json` (JSON), `summary`, `original_filename`, `created_at`, `updated_at`
- [ ] Create `Section` model with fields: `id` (PK), `section_id`, `doc_id` (FK), `parent_section_id`, `title`, `summary`, `page_start`, `page_end`, `heading_level`, `section_path` (JSON)
- [ ] Create `Paragraph` model with fields: `para_id` (PK, String(100)), `doc_id` (FK), `section_id`, `para_index`, `text`, `markdown_source`, `page_number`, `section_path` (JSON)
- [ ] Add composite index on `(doc_id, section_id)` for sections and paragraphs
- [ ] Add cascade delete relationships: Document → Sections, Document → Paragraphs

---

### L1-S-002: SQLAlchemy Models — Supporting Tables [P1]

**Stream**: Storage
**Files**: `app/storage/models.py`
**Dependencies**: L1-S-001
**Interfaces**: `CrossReference`, `IngestionCheckpoint` classes

**Acceptance Criteria**:
- [ ] Create `CrossReference` model with fields: `id` (PK), `source_para_id` (FK), `source_text`, `target_doc_id`, `target_node_id`, `resolved` (bool), `created_at`
- [ ] Create `IngestionCheckpoint` model with fields: `doc_id` (PK), `stage`, `stage_data` (JSON), `error_message`, `created_at`, `updated_at`
- [ ] Add indexes on cross-reference source and target columns
- [ ] Add cascade delete from Paragraph to CrossReference

---

### L1-S-003: SQLAlchemy Models — Cache Tables [P1]

**Stream**: Storage
**Files**: `app/storage/models.py`
**Dependencies**: L1-S-001
**Interfaces**: `QueryCache`, `ReasoningTrace`, `QueryLog`, `UserFeedback` classes

**Acceptance Criteria**:
- [ ] Create `QueryCache` model (L4): `query_hash` (PK), `query_text`, `doc_scope` (JSON), `answer`, `confidence`, `citations` (JSON), `evidence_log` (JSON), `sections_explored` (JSON), `iterations`, `created_at`
- [ ] Create `ReasoningTrace` model (L5): `query_id` (PK, UUID), `query_text`, `trace_json` (JSON), `answer`, `latency_ms`, `iterations`, `created_at`
- [ ] Create `QueryLog` model: `id` (PK), `query_id`, `query_text`, `user_language`, `cache_hit`, `latency_ms`, `iterations`, `confidence`, `created_at`
- [ ] Create `UserFeedback` model: `id` (PK), `query_id`, `rating`, `category`, `details`, `created_at`
- [ ] Add index on `QueryCache.created_at`

---

### L1-S-004: SQLAlchemy Models — Embedding Table [P2]

**Stream**: Storage
**Files**: `app/storage/models.py`
**Dependencies**: L1-S-001
**Interfaces**: `Embedding` class

**Acceptance Criteria**:
- [x] Create `Embedding` model: `para_id` (PK, FK to paragraphs), `vector` (LargeBinary), `model_name`, `created_at`
- [x] Add cascade delete from Paragraph to Embedding
- [x] Document that vector is serialized numpy array

---

### L1-S-005: Database Connection [P1]

**Stream**: Storage
**Files**: `app/storage/database.py`
**Dependencies**: L0-003, L1-S-001
**Interfaces**: `engine`, `AsyncSessionLocal`, `init_db()`, `get_db()` dependency

**Acceptance Criteria**:
- [ ] Create async engine from `settings.database_url`
- [ ] Create `AsyncSessionLocal` sessionmaker with `expire_on_commit=False`
- [ ] Implement `async def init_db()` that creates all tables
- [ ] Implement `async def get_db()` as FastAPI dependency yielding sessions
- [ ] Add proper connection cleanup on session close
- [ ] Test with in-memory SQLite: `sqlite+aiosqlite:///:memory:`

---

### L1-S-006: Repository Layer — Documents [P1]

**Stream**: Storage
**Files**: `app/storage/repositories.py`
**Dependencies**: L1-S-001, L1-S-005
**Interfaces**: `DocumentRepository` class with CRUD operations

**Acceptance Criteria**:
- [ ] Implement `DocumentRepository` class accepting `AsyncSession`
- [ ] Method: `async def create(doc_id, title, file_type, ...) -> Document`
- [ ] Method: `async def get_by_id(doc_id) -> Document | None`
- [ ] Method: `async def list_documents(topic=None, language=None) -> list[Document]`
- [ ] Method: `async def delete(doc_id) -> bool` with cascade handling
- [ ] Method: `async def get_by_file_hash(file_hash) -> Document | None` for dedup
- [ ] Topic filtering searches title and summary fields
- [ ] All methods use async/await properly

---

### L1-S-007: Repository Layer — Paragraphs & Search [P1]

**Stream**: Storage
**Files**: `app/storage/repositories.py`
**Dependencies**: L1-S-001, L1-S-005
**Interfaces**: `ParagraphRepository` class with search operations

**Acceptance Criteria**:
- [ ] Implement `ParagraphRepository` class accepting `AsyncSession`
- [ ] Method: `async def create_bulk(paragraphs: list[Paragraph]) -> int`
- [ ] Method: `async def get_by_ids(para_ids: list[str]) -> list[Paragraph]`
- [ ] Method: `async def get_by_section(doc_id, section_id) -> list[Paragraph]`
- [ ] Method: `async def search_text(query, doc_ids=None, regex=False, limit=10) -> list[dict]`
- [ ] Text search uses SQLite LIKE or regex via Python re module
- [ ] Return results include: `para_id`, `text`, `page_number`, `section_path`, `doc_id`
- [ ] Handle regex compilation errors gracefully

---

### L1-S-008: Cache Manager [P1]

**Stream**: Storage
**Files**: `app/storage/cache.py`
**Dependencies**: L1-S-003, L1-S-005
**Interfaces**: `CacheManager` class for L1-L5 cache operations

**Acceptance Criteria**:
- [ ] Implement `CacheManager` class accepting `AsyncSession`
- [ ] L1: `async def get_ingestion_cache(file_hash) -> Document | None`
- [ ] L2: `get_toc_corpus() -> dict` (in-memory), `invalidate_toc_corpus()`
- [ ] L4: `async def get_query_result(query, doc_scope) -> dict | None`
- [ ] L4: `async def cache_query_result(query, doc_scope, result)`
- [ ] L5: `async def store_reasoning_trace(query_id, query_text, trace, answer, latency_ms)`
- [ ] `async def invalidate_for_document(doc_id)` — clears L2, L4 for affected queries
- [ ] Implement `_compute_query_hash(query, doc_scope)` using SHA-256

---

## Stream: INGESTION (Agent 2)

### L1-I-001: Docling Parser Wrapper [P1]

**Stream**: Ingestion
**Files**: `app/ingestion/docling_parser.py`
**Dependencies**: L0-003
**Interfaces**: `DoclingParser` class with `parse()` method

**Acceptance Criteria**:
- [ ] Implement `DoclingParser` class
- [ ] Method: `async def parse(file_path: Path) -> tuple[str, dict]`
- [ ] Returns: `(markdown_content, metadata_dict)`
- [ ] Metadata includes: `title`, `page_count`, `file_type`
- [ ] Title fallback: use filename stem if document has no title
- [ ] Handle Docling exceptions gracefully with clear error messages
- [ ] Validate file exists before parsing

---

### L1-I-002: File Validation [P1]

**Stream**: Ingestion
**Files**: `app/ingestion/docling_parser.py`
**Dependencies**: L1-I-001
**Interfaces**: `validate_file()` function

**Acceptance Criteria**:
- [ ] Implement `def validate_file(file_path: Path) -> bool`
- [ ] Check file extension: `.pdf`, `.docx`, `.pptx`
- [ ] Check MIME type using `python-magic` or manual signature detection
- [ ] Allowed MIME types:
  - `application/pdf`
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - `application/vnd.openxmlformats-officedocument.presentationml.presentation`
- [ ] Return `False` for invalid files, don't raise exceptions

---

### L1-I-003: Markdown Structure Analyzer [P1]

**Stream**: Ingestion
**Files**: `app/ingestion/structure.py`
**Dependencies**: L0-001
**Interfaces**: `Section` dataclass, `MarkdownStructureAnalyzer` class

**Acceptance Criteria**:
- [ ] Create `Section` dataclass with fields: `section_id`, `title`, `heading_level`, `content`, `page_start`, `page_end`, `parent_id`, `children`
- [ ] Implement `MarkdownStructureAnalyzer` class
- [ ] Method: `def analyze(markdown: str) -> list[Section]`
- [ ] Detect headings via regex: `^(#{1,6})\s+(.+)$`
- [ ] Generate section IDs: `s1`, `s1.1`, `s1.1.2`, etc.
- [ ] Track parent-child relationships based on heading levels
- [ ] Extract content between headings
- [ ] Handle documents with no headings (create single root section)

---

### L1-I-004: Paragraph Extractor [P1]

**Stream**: Ingestion
**Files**: `app/ingestion/structure.py`
**Dependencies**: L1-I-003
**Interfaces**: `Paragraph` dataclass, `ParagraphExtractor` class

**Acceptance Criteria**:
- [ ] Create `Paragraph` dataclass with fields: `para_id`, `text`, `section_id`, `para_index`, `markdown_source`
- [ ] Implement `ParagraphExtractor` class
- [ ] Method: `def extract(doc_id: str, sections: list[Section]) -> list[Paragraph]`
- [ ] Split section content on double newlines (`\n\n+`)
- [ ] Generate para_id format: `{doc_id}:{section_id}:p{index:03d}`
- [ ] Skip empty paragraphs
- [ ] Preserve original markdown in `markdown_source`
- [ ] 1-based paragraph indexing within each section

---

### L1-I-005: Haiku Annotator [P1]

**Stream**: Ingestion
**Files**: `app/ingestion/annotator.py`
**Dependencies**: L0-003
**Interfaces**: `HaikuAnnotator` class with `annotate_section()` method

**Acceptance Criteria**:
- [ ] Implement `HaikuAnnotator` class using Anthropic client
- [ ] Use model from `settings.annotation_model` (claude-3-5-haiku)
- [ ] Method: `async def annotate_section(title: str, content: str, context: str = "") -> dict`
- [ ] Return JSON with keys: `summary`, `language`, `topics`, `cross_references`
- [ ] Summary: 1-3 sentences based on content complexity
- [ ] Language: detect from content (de, fr, it, en)
- [ ] Truncate content to 3000 chars for token limits
- [ ] Handle API errors with retry logic (3 attempts)
- [ ] Parse JSON response safely with fallback defaults

---

### L1-I-006: Cross-Reference Extractor [P1]

**Stream**: Ingestion
**Files**: `app/ingestion/cross_references.py`
**Dependencies**: L0-001
**Interfaces**: `CrossReferenceExtractor` class

**Acceptance Criteria**:
- [ ] Implement `CrossReferenceExtractor` class
- [ ] Method: `def extract(text: str) -> list[dict]`
- [ ] Detect multilingual reference patterns:
  - English: `see Section X`, `refer to Appendix Y`
  - German: `siehe Abschnitt X`, `gemäss Anhang Y`
  - French: `voir chapitre X`, `selon Annexe Y`
  - Italian: `vedi sezione X`, `secondo Allegato Y`
- [ ] Return list of dicts: `{source_text, target_hint}`
- [ ] Case-insensitive matching
- [ ] Extract section numbers, appendix letters, document names

---

### L1-I-007: Checkpoint Manager [P1]

**Stream**: Ingestion
**Files**: `app/ingestion/checkpoints.py`
**Dependencies**: L1-S-002, L1-S-005
**Interfaces**: `CheckpointManager` class for resumable ingestion

**Acceptance Criteria**:
- [ ] Implement `CheckpointManager` class accepting `AsyncSession`
- [ ] Method: `async def get(doc_id: str) -> IngestionCheckpoint | None`
- [ ] Method: `async def save(doc_id: str, stage: str, stage_data: dict)`
- [ ] Method: `async def delete(doc_id: str)` — clear on success
- [ ] Method: `async def update_error(doc_id: str, error_msg: str)`
- [ ] Valid stages: `parsing`, `structure`, `paragraphs`, `annotation`, `cross_refs`, `indexing`
- [ ] Upsert behavior: create or update checkpoint
- [ ] Store stage_data as JSON blob

---

### L1-I-008: DOCX/PPTX Verification [P2]

**Stream**: Ingestion
**Files**: `app/ingestion/docling_parser.py`
**Dependencies**: L1-I-001
**Interfaces**: Updated `DoclingParser` with format-specific handling

**Acceptance Criteria**:
- [x] Test Docling with DOCX files — verify heading extraction quality
- [x] Test Docling with PPTX files — verify slide-to-section mapping
- [x] Add format-specific metadata extraction (e.g., slide count for PPTX)
- [x] Document any format-specific quirks in code comments
- [x] Create test fixtures: one sample DOCX, one sample PPTX

---

## Stream: CORE (Agent 3)

### L1-C-001: System Prompt Template [P1]

**Stream**: Core
**Files**: `app/core/prompts.py`
**Dependencies**: L0-001
**Interfaces**: `SYSTEM_PROMPT` template string

**Acceptance Criteria**:
- [ ] Create `SYSTEM_PROMPT` constant with XML-tagged sections
- [ ] Include `<role>` section: document research assistant for Caritas Switzerland
- [ ] Include `<reasoning_protocol>` section: 9-step reasoning process
- [ ] Include `<citation_rules>` section: format requirements, no invention
- [ ] Include `<cross_reference_rules>` section: how to follow references
- [ ] Include `<gap_reporting>` section: what to do when evidence insufficient
- [ ] Include `<language>` section: respond in query language, handle multilingual
- [ ] Include `<out_of_scope>` section: how to handle unrelated questions
- [ ] Include `{toc_corpus}` placeholder for dynamic ToC injection

---

### L1-C-002: Tool Schema Definitions [P1]

**Stream**: Core
**Files**: `app/core/tools.py`
**Dependencies**: L0-001
**Interfaces**: `TOOLS` list for Anthropic API

**Acceptance Criteria**:
- [ ] Define `TOOLS` list with 7 tool schemas matching Anthropic format
- [ ] Tool 1: `list_documents` — optional topic/language filters
- [ ] Tool 2: `get_toc` — required doc_id
- [ ] Tool 3: `read_section` — required doc_id, node_id
- [ ] Tool 4: `read_paragraphs` — required para_ids array
- [ ] Tool 5: `grep_documents` — required query_text, optional doc_ids/regex/context/max_results
- [ ] Tool 6: `search_fallback` — required query_text, optional doc_ids/top_k (Phase 2 stub)
- [ ] Tool 7: `record_evidence` — required para_id, relevance_note
- [ ] All schemas have descriptions matching plan.md Section 7

---

### L1-C-003: Evidence Tracking [P1]

**Stream**: Core
**Files**: `app/core/evidence.py`
**Dependencies**: L0-001
**Interfaces**: `EvidenceVerifier` class

**Acceptance Criteria**:
- [ ] Implement `EvidenceVerifier` class
- [ ] Method: `def extract_citations(answer: str) -> list[dict]`
  - Parse `[Document Title, Section X.Y, p.N]` format
  - Return list of `{doc_title, section, page, text_snippet}`
- [ ] Method: `def verify(citations, evidence_log) -> tuple[list, list]`
  - Return `(verified_citations, unverified_citations)`
  - Match citations to para_ids in evidence log
- [ ] Method: `def match_quotes(quote: str, evidence_texts: list[str]) -> bool`
  - Fuzzy match for minor LLM paraphrasing
  - Use Levenshtein distance or similar (threshold: 85% similarity)

---

### L1-C-004: Confidence Calculator [P1]

**Stream**: Core
**Files**: `app/core/evidence.py`
**Dependencies**: L1-C-003
**Interfaces**: `calculate_confidence()` function

**Acceptance Criteria**:
- [ ] Implement `def calculate_confidence(evidence_log, citations) -> dict`
- [ ] Return `{level, statement}` where level is "high", "medium", or "low"
- [ ] High: ≥3 evidence items AND ≥2 citations
- [ ] Medium: ≥1 evidence item
- [ ] Low: no evidence items
- [ ] Statements should be human-readable, e.g., "Confidence: High - direct evidence from multiple sources"

---

### L1-C-005: Citation Regeneration [P1]

**Stream**: Core
**Files**: `app/core/evidence.py`
**Dependencies**: L1-C-003
**Interfaces**: `regenerate_with_strict_citations()` function

**Acceptance Criteria**:
- [ ] Implement `async def regenerate_with_strict_citations(answer, evidence_log, client) -> str`
- [ ] Call Claude to rewrite answer using only verified evidence
- [ ] Prompt specifies exact para_ids that can be cited
- [ ] If still fails verification, add warning prefix to answer
- [ ] Limit to 1 regeneration attempt to bound cost

---

### L1-C-006: Timeout Wrapper [P1]

**Stream**: Core
**Files**: `app/core/orchestrator.py` (partial)
**Dependencies**: L0-003
**Interfaces**: `with_timeout()` async context manager

**Acceptance Criteria**:
- [ ] Implement `async def with_timeout(coro, timeout_seconds)` wrapper
- [ ] Use `asyncio.wait_for()` with `settings.query_timeout_seconds`
- [ ] Raise custom `QueryTimeoutError` on timeout
- [ ] Include elapsed time in error message
- [ ] Ensure proper cleanup of cancelled tasks

---

## Stream: API (Agent 4)

### L1-A-001: Pydantic Schemas — Request [P1]

**Stream**: API
**Files**: `app/api/schemas.py`
**Dependencies**: L0-001
**Interfaces**: `QueryRequest`, `DocumentUploadResponse` models

**Acceptance Criteria**:
- [ ] Create `QueryRequest` model: `question: str`, `doc_ids: list[str] | None = None`
- [ ] Create `DocumentUploadResponse`: `doc_id: str`, `status: str`, `filename: str`
- [ ] Create `FeedbackRequest`: `rating: str`, `category: str | None`, `details: str | None`
- [ ] Add validation: question min length 3 chars
- [ ] Add validation: rating must be "thumbs_up" or "thumbs_down"

---

### L1-A-002: Pydantic Schemas — Response [P1]

**Stream**: API
**Files**: `app/api/schemas.py`
**Dependencies**: L1-A-001
**Interfaces**: `Citation`, `QueryResponse`, `ProgressEvent` models

**Acceptance Criteria**:
- [ ] Create `Citation` model: `para_id`, `doc_title`, `section`, `page`, `text_snippet`, `original_url`
- [ ] Create `QueryResponse` model: `query_id`, `answer`, `confidence`, `confidence_statement`, `citations: list[Citation]`, `gaps: str | None`, `sections_explored: list[str]`, `iterations: int`, `latency_breakdown: dict`
- [ ] Create `ProgressEvent` model: `iteration: int`, `tool: str`, `status: str`
- [ ] Create `DocumentInfo` model: `doc_id`, `title`, `language`, `total_pages`, `file_type`, `created_at`

---

### L1-A-003: Query Routes — Stub [P1]

**Stream**: API
**Files**: `app/api/routes/query.py`
**Dependencies**: L1-A-001, L1-A-002
**Interfaces**: `router` with `/query` and `/query/{id}/stream` stubs

**Acceptance Criteria**:
- [ ] Create `APIRouter` with prefix `/api`
- [ ] Stub `POST /query` endpoint — returns query_id and "processing" status
- [ ] Stub `GET /query/{query_id}/stream` endpoint — returns EventSourceResponse placeholder
- [ ] Stub `POST /query/{query_id}/feedback` endpoint
- [ ] Add type hints for all route parameters
- [ ] Add docstrings describing endpoint purpose

---

### L1-A-004: Document Routes — Stub [P1]

**Stream**: API
**Files**: `app/api/routes/documents.py`
**Dependencies**: L1-A-001, L1-A-002
**Interfaces**: `router` with document management endpoints

**Acceptance Criteria**:
- [ ] Create `APIRouter` with prefix `/api/documents`
- [ ] Stub `POST /upload` endpoint — accepts `UploadFile`
- [ ] Stub `GET /` endpoint — list all documents
- [ ] Stub `GET /{doc_id}` endpoint — get document details
- [ ] Stub `DELETE /{doc_id}` endpoint — delete document
- [ ] Add file type validation in upload route
- [ ] Add proper HTTPException for 404 cases

---

### L1-A-005: Dependencies Module [P1]

**Stream**: API
**Files**: `app/dependencies.py`
**Dependencies**: L1-S-005, L1-S-008
**Interfaces**: Dependency injection functions

**Acceptance Criteria**:
- [ ] Re-export `get_db` from `app.storage.database`
- [ ] Create `get_cache_manager` dependency returning `CacheManager`
- [ ] Create `get_document_repository` dependency
- [ ] Create `get_paragraph_repository` dependency
- [ ] All dependencies properly typed with return annotations

---

### L1-A-006: Admin Routes — Stub [P3]

**Stream**: API
**Files**: `app/api/routes/admin.py`
**Dependencies**: L1-A-002
**Interfaces**: `router` with admin endpoint stubs

**Acceptance Criteria**:
- [ ] Create `APIRouter` with prefix `/api/admin`
- [ ] Stub `GET /cache/stats` endpoint — cache hit rates
- [ ] Stub `POST /cache/invalidate` endpoint — manual invalidation
- [ ] Stub `GET /queries/recent` endpoint — recent query log
- [ ] Stub `GET /traces/{query_id}` endpoint — reasoning trace viewer
- [ ] Stub `GET /config` and `PUT /config` endpoints — runtime settings

---

## Stream: TESTS (Agent 5)

### L1-T-001: Pytest Configuration [P1]

**Stream**: Tests
**Files**: `tests/conftest.py`
**Dependencies**: L0-002, L1-S-005
**Interfaces**: Core pytest fixtures

**Acceptance Criteria**:
- [ ] Create `db_session` fixture: in-memory SQLite async session
- [ ] Create `client` fixture: `httpx.AsyncClient` for FastAPI testing
- [ ] Create `mock_anthropic_client` fixture using pytest-mock
- [ ] Create `sample_markdown` fixture with heading structure
- [ ] Set `asyncio_mode = "auto"` in pytest config
- [ ] Add `pytest.mark.asyncio` decorator helper

---

### L1-T-002: Test Document Fixtures [P1]

**Stream**: Tests
**Files**: `tests/fixtures/sample_documents/`
**Dependencies**: L0-001
**Interfaces**: Sample test documents

**Acceptance Criteria**:
- [ ] Create `test_policy.md` — simple markdown with 3-level headings
- [ ] Create structure: Introduction, Section 1 (1.1, 1.2), Section 2, Appendix A
- [ ] Include cross-reference text: "see Section 1.2", "gemäss Appendix A"
- [ ] Create `test_policy_de.md` — German version
- [ ] Total: ~50 paragraphs across ~10 sections
- [ ] Include realistic policy content (password policies, access control, etc.)

---

### L1-T-003: Mock Anthropic Responses [P1]

**Stream**: Tests
**Files**: `tests/fixtures/mock_responses/`
**Dependencies**: L0-001
**Interfaces**: Mock API response data

**Acceptance Criteria**:
- [ ] Create `tool_use_responses.py` with mock tool_use messages
- [ ] Create `final_answer_responses.py` with mock end_turn messages
- [ ] Create `annotation_responses.py` with mock Haiku outputs
- [ ] Include realistic message IDs and structure
- [ ] Cover scenarios: single tool call, multi-tool, final answer
- [ ] Add helper function to construct mock Message objects

---

### L1-T-004: Unit Test Templates [P1]

**Stream**: Tests
**Files**: `tests/unit/`
**Dependencies**: L1-T-001
**Interfaces**: Unit test file structure

**Acceptance Criteria**:
- [ ] Create `test_structure.py` with placeholder tests for `MarkdownStructureAnalyzer`
- [ ] Create `test_tools.py` with placeholder tests for tool handlers
- [ ] Create `test_annotator.py` with placeholder tests for `HaikuAnnotator`
- [ ] Create `test_evidence.py` with placeholder tests for `EvidenceVerifier`
- [ ] Create `test_cache.py` with placeholder tests for `CacheManager`
- [ ] Create `test_cross_refs.py` with placeholder tests for `CrossReferenceExtractor`
- [ ] Each file has at least 3 test function stubs with descriptive names

---

### L1-T-005: Integration Test Templates [P1]

**Stream**: Tests
**Files**: `tests/integration/`
**Dependencies**: L1-T-001
**Interfaces**: Integration test file structure

**Acceptance Criteria**:
- [ ] Create `test_ingestion.py` with placeholder for full pipeline test
- [ ] Create `test_orchestrator.py` with placeholder for reasoning loop test
- [ ] Create `test_api.py` with placeholder for endpoint tests
- [ ] Create `test_sse.py` with placeholder for SSE streaming tests
- [ ] Each file imports relevant fixtures from conftest
- [ ] Add `@pytest.mark.integration` marker to all tests

---

### L1-T-006: 10 Test Questions [P1]

**Stream**: Tests
**Files**: `tests/fixtures/test_questions.py`
**Dependencies**: L1-T-002
**Interfaces**: `TEST_QUESTIONS` list for evaluation

**Acceptance Criteria**:
- [ ] Create 10 question-answer pairs covering:
  - 3 factual lookup (single doc)
  - 2 factual lookup (specific section)
  - 2 synthesis (single doc)
  - 1 cross-reference following
  - 1 unanswerable question
  - 1 out-of-scope question
- [ ] Each entry: `{question, expected_source, expected_answer_keywords, category}`
- [ ] Include expected section/page references
- [ ] Cover DE and EN questions

---

## Stream: SCRIPTS & CONFIG (Agent 6)

### L1-X-001: Database Initialization Script [P1]

**Stream**: Scripts
**Files**: `scripts/init_db.py`
**Dependencies**: L1-S-005
**Interfaces**: CLI script to create database

**Acceptance Criteria**:
- [ ] Create runnable script: `python scripts/init_db.py`
- [ ] Load settings from environment
- [ ] Create database directory if needed
- [ ] Call `init_db()` to create all tables
- [ ] Print confirmation message with database path
- [ ] Handle existing database gracefully (no-op or warn)

---

### L1-X-002: Gitignore Configuration [P1]

**Stream**: Scripts
**Files**: `.gitignore`
**Dependencies**: L0-001
**Interfaces**: Standard Python .gitignore

**Acceptance Criteria**:
- [ ] Ignore Python artifacts: `__pycache__/`, `*.pyc`, `*.pyo`, `.ruff_cache/`
- [ ] Ignore environment: `.env`, `.venv/`, `venv/`
- [ ] Ignore data directories: `data/`, `documents/`
- [ ] Ignore IDE files: `.vscode/`, `.idea/`
- [ ] Ignore test artifacts: `.pytest_cache/`, `.coverage`, `htmlcov/`
- [ ] Ignore macOS files: `.DS_Store`

---

### L1-X-003: README Documentation [P1]

**Stream**: Scripts
**Files**: `README.md`
**Dependencies**: L0-002, L0-003
**Interfaces**: User-facing documentation

**Acceptance Criteria**:
- [ ] Project title and description
- [ ] Prerequisites: Python 3.12+, Anthropic API key
- [ ] Installation steps: venv, pip install, env setup
- [ ] Database initialization command
- [ ] Running the server: uvicorn command
- [ ] Running tests: pytest command
- [ ] API documentation link (FastAPI /docs)
- [ ] Architecture overview referencing plan/plan.md

---

### L1-X-004: Development Scripts [P1]

**Stream**: Scripts
**Files**: `scripts/seed_test_data.py`
**Dependencies**: L1-S-006, L1-T-002
**Interfaces**: CLI script to seed test data

**Acceptance Criteria**:
- [ ] Create runnable script: `python scripts/seed_test_data.py`
- [ ] Load test markdown fixtures
- [ ] Parse structure and create documents/sections/paragraphs
- [ ] Insert into database using repositories
- [ ] Print summary: N documents, M sections, P paragraphs
- [ ] Idempotent: skip if data exists

---

### L1-X-005: Type Stubs [P1]

**Stream**: Scripts
**Files**: `py.typed`, stubs as needed
**Dependencies**: L0-002
**Interfaces**: Type checking configuration

**Acceptance Criteria**:
- [ ] Create `py.typed` marker file in `app/`
- [ ] Run `mypy app/` and fix any configuration issues
- [ ] Document any type ignore comments with reasoning
- [ ] Ensure all public functions have type hints
- [ ] Add `--strict` to mypy config in pyproject.toml

---

## Level 2: Integration Tasks

**Estimated Time:** 1-2 weeks per stream
**Required Before:** Level 3 tests
**Agent Count:** 4 (parallel work)

---

## Stream: ORCHESTRATOR (requires Core + Storage)

### L2-O-001: Tool Handler Implementation [P1]

**Stream**: Orchestrator
**Files**: `app/core/tools.py`
**Dependencies**: L1-C-002, L1-S-006, L1-S-007
**Interfaces**: `ToolHandler` class with `execute()` method

**Acceptance Criteria**:
- [ ] Implement `ToolHandler` class accepting `AsyncSession`
- [ ] Initialize repositories: `DocumentRepository`, `ParagraphRepository`
- [ ] Maintain state: `evidence_log: list[dict]`, `visited_sections: set[str]`
- [ ] Implement `async def execute(tool_name: str, tool_input: dict) -> Any`
- [ ] Route to handlers: `_list_documents`, `_get_toc`, `_read_section`, `_read_paragraphs`, `_grep_documents`, `_record_evidence`
- [ ] `_search_fallback` raises `NotImplementedError` (Phase 2)
- [ ] `_read_section` adds to `visited_sections`
- [ ] `_record_evidence` adds to `evidence_log` with iteration number
- [ ] Handle errors gracefully: return `{error: message}` dict

---

### L2-O-002: Orchestrator Core Loop [P1]

**Stream**: Orchestrator
**Files**: `app/core/orchestrator.py`
**Dependencies**: L2-O-001, L1-C-001, L1-C-003, L1-S-008
**Interfaces**: `ReasoningOrchestrator` class

**Acceptance Criteria**:
- [ ] Implement `ReasoningOrchestrator` class accepting `AsyncSession`
- [ ] Initialize: Anthropic client, ToolHandler, EvidenceVerifier, CacheManager
- [ ] Implement `async def run(question: str, doc_ids: list[str] | None = None) -> dict`
- [ ] Load ToC corpus from cache
- [ ] Format system prompt with ToC
- [ ] Loop up to `settings.max_reasoning_iterations`:
  - Call Claude with tools
  - If `stop_reason == "end_turn"`: verify citations, return answer
  - If tool_use: execute tool, add result to messages
- [ ] Handle max iterations: synthesize partial answer
- [ ] Apply query timeout wrapper

---

### L2-O-003: SSE Progress Streaming [P1]

**Stream**: Orchestrator
**Files**: `app/core/orchestrator.py`
**Dependencies**: L2-O-002
**Interfaces**: `run_with_progress()` async generator

**Acceptance Criteria**:
- [ ] Implement `async def run_with_progress(query_id, question, doc_ids) -> AsyncIterator[dict]`
- [ ] Yield progress events: `{type: "progress", data: {iteration, tool, status}}`
- [ ] Yield answer event: `{type: "answer", data: QueryResponse}`
- [ ] Events are JSON-serializable
- [ ] Progress emitted before each tool call
- [ ] Include timing information in final answer
- [ ] Handle errors: yield `{type: "error", data: {error: message}}`

---

### L2-O-004: search_fallback Implementation [P2]

**Stream**: Orchestrator
**Files**: `app/core/tools.py`, `app/storage/embeddings.py`
**Dependencies**: L2-O-001, L1-S-004
**Interfaces**: `EmbeddingSearch` class, `_search_fallback` handler

**Acceptance Criteria**:
- [x] Create `app/storage/embeddings.py` with `EmbeddingSearch` class
- [x] Use `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model
- [x] Load FAISS index from persisted file on startup
- [x] Implement `async def search(query, doc_ids, top_k) -> list[dict]`
- [x] Return: `{para_id, text, score, doc_id, section_path}`
- [x] Filter by doc_ids if provided
- [x] Update `_search_fallback` in ToolHandler to call EmbeddingSearch
- [x] Add embedding generation to ingestion pipeline

---

## Stream: INGESTION PIPELINE (requires Ingestion + Storage)

### L2-P-001: Pipeline Coordinator [P1]

**Stream**: Pipeline
**Files**: `app/ingestion/pipeline.py`
**Dependencies**: L1-I-001 through L1-I-007, L1-S-006, L1-S-007
**Interfaces**: `IngestionPipeline` class with `ingest()` method

**Acceptance Criteria**:
- [ ] Implement `IngestionPipeline` class accepting `AsyncSession`
- [ ] Initialize all components: parser, analyzer, extractor, annotator, checkpoint_mgr, repositories
- [ ] Define stages: `["parsing", "structure", "paragraphs", "annotation", "cross_refs", "indexing"]`
- [ ] Implement `async def ingest(file_path: Path, doc_id: str | None = None) -> str`
- [ ] Generate doc_id if not resuming: `str(uuid4())[:12]`
- [ ] Check for existing checkpoint and resume from that stage
- [ ] Execute stages sequentially with checkpoint saves
- [ ] Clear checkpoint on successful completion
- [ ] Raise `IngestionError` on failure with stage info

---

### L2-P-002: ToC JSON Builder [P1]

**Stream**: Pipeline
**Files**: `app/ingestion/pipeline.py`
**Dependencies**: L2-P-001
**Interfaces**: `_build_toc_json()` method

**Acceptance Criteria**:
- [ ] Implement `def _build_toc_json(sections: list[Section]) -> dict`
- [ ] Build hierarchical tree structure from flat section list
- [ ] Each node has: `node_id`, `title`, `summary`, `page_range`, `paragraph_count`, `cross_references`, `sub_nodes`
- [ ] Root level contains top-level sections (heading level 1)
- [ ] Nested sections appear in parent's `sub_nodes`
- [ ] Return structure matches CLAUDE.md ToC node format

---

### L2-P-003: Cross-Reference Indexing [P2]

**Stream**: Pipeline
**Files**: `app/ingestion/pipeline.py`, `app/storage/repositories.py`
**Dependencies**: L2-P-001, L1-S-002
**Interfaces**: `CrossReferenceRepository` class, cross-ref resolution logic

**Acceptance Criteria**:
- [x] Implement `CrossReferenceRepository` with CRUD operations
- [x] In pipeline: after extraction, attempt to resolve cross-references
- [x] Resolution: match target_hint to section titles or appendix names
- [x] Set `resolved=True` if target found, store `target_doc_id` and `target_node_id`
- [x] Store unresolved references for admin review
- [x] Add `get_unresolved(doc_id)` method to repository
- [x] Add cross_references list to ToC node JSON

---

## Stream: FASTAPI APP (requires API + Core)

### L2-F-001: Application Entry Point [P1]

**Stream**: FastAPI
**Files**: `app/main.py`
**Dependencies**: L1-A-003, L1-A-004, L1-S-005, L1-S-008
**Interfaces**: `app` FastAPI instance

**Acceptance Criteria**:
- [ ] Create FastAPI app with title, description, version
- [ ] Implement `lifespan` context manager:
  - Startup: call `init_db()`, load ToC corpus into cache
  - Shutdown: cleanup if needed
- [ ] Include routers: query, documents (admin in Phase 3)
- [ ] Add CORS middleware for development
- [ ] Mount static files at `/static`
- [ ] Add health check endpoint: `GET /health`

---

### L2-F-002: Query Routes — Full Implementation [P1]

**Stream**: FastAPI
**Files**: `app/api/routes/query.py`
**Dependencies**: L2-O-003, L1-S-008, L1-A-002
**Interfaces**: Complete query endpoints

**Acceptance Criteria**:
- [ ] `POST /query`:
  - Check cache first, return immediately if hit
  - Generate query_id, store in processing queue
  - Log query start
  - Return `{query_id, status, stream_url}`
- [ ] `GET /query/{query_id}/stream`:
  - Create EventSourceResponse with event generator
  - Call `orchestrator.run_with_progress()`
  - Emit progress and answer events as SSE
  - Cache result on completion
  - Store reasoning trace (L5)
  - Log query completion
- [ ] `POST /query/{query_id}/feedback`:
  - Store feedback in database
  - Return confirmation

---

### L2-F-003: Document Routes — Full Implementation [P1]

**Stream**: FastAPI
**Files**: `app/api/routes/documents.py`
**Dependencies**: L2-P-001, L1-S-006, L1-S-008
**Interfaces**: Complete document endpoints

**Acceptance Criteria**:
- [ ] `POST /upload`:
  - Validate file extension (.pdf, .docx, .pptx)
  - Generate doc_id, create directory
  - Save file to `documents/{doc_id}/original.{ext}`
  - Run ingestion pipeline
  - Return DocumentUploadResponse
  - Clean up on failure
- [ ] `GET /`:
  - List all documents from repository
  - Return list of DocumentInfo
- [ ] `GET /{doc_id}`:
  - Get document by ID
  - Include ToC in response
  - Return 404 if not found
- [ ] `DELETE /{doc_id}`:
  - Delete from database (cascade)
  - Invalidate caches
  - Delete files from filesystem
  - Return confirmation

---

### L2-F-004: Error Handling [P1]

**Stream**: FastAPI
**Files**: `app/main.py`, `app/api/exceptions.py`
**Dependencies**: L2-F-001
**Interfaces**: Global exception handlers

**Acceptance Criteria**:
- [ ] Create `app/api/exceptions.py` with custom exceptions:
  - `IngestionError`
  - `QueryTimeoutError`
  - `DocumentNotFoundError`
  - `ValidationError`
- [ ] Add global exception handlers in main.py
- [ ] Return consistent error response format: `{error: str, detail: str | None}`
- [ ] Log all errors with traceback
- [ ] Don't expose internal details in production

---

### L2-F-005: Logging Configuration [P1]

**Stream**: FastAPI
**Files**: `app/logging_config.py`
**Dependencies**: L0-003
**Interfaces**: Configured logger for application

**Acceptance Criteria**:
- [ ] Create logging configuration using `settings.log_level`
- [ ] JSON format for production, readable format for development
- [ ] Include: timestamp, level, module, message
- [ ] Log to stdout (containerization-friendly)
- [ ] Create logger factory: `get_logger(name: str)`
- [ ] Add request logging middleware

---

## Stream: WEB UI (Phase 2)

**Status Update (2026-02-22):**
- [x] Phase 2 UI routes and templates implemented (`/ui`, citation panel, feedback partial)
- [x] Static assets wired in FastAPI (`/static` from `app/ui/static`)
- [x] HTML-first navigation available from browser root (`GET /` with `Accept: text/html` redirects to `/ui`)

### L2-U-001: Base Template [P2]

**Stream**: UI
**Files**: `app/ui/templates/base.html`, `app/ui/static/css/styles.css`
**Dependencies**: L0-001
**Interfaces**: Jinja2 base template

**Acceptance Criteria**:
- [x] Create base.html with:
  - DOCTYPE, html lang, charset, viewport
  - Block: title, head, content
  - htmx.min.js script tag
  - styles.css link
- [x] Create styles.css with:
  - CSS reset/normalize
  - Typography (system fonts)
  - Layout utilities
  - Form styling
  - Card/panel components
- [x] Download htmx.min.js to static/js/

---

### L2-U-002: Query Page [P2]

**Stream**: UI
**Files**: `app/ui/templates/query.html`, `app/api/routes/ui.py`
**Dependencies**: L2-U-001, L2-F-002
**Interfaces**: Main query interface

**Acceptance Criteria**:
- [x] Create query.html extending base.html
- [x] Question input form with htmx POST to /api/query
- [x] Progress indicator div with SSE connection
- [x] Results div for answer display
- [x] Citation rendering with clickable references
- [x] Create ui.py router for serving templates
- [x] Add `GET /` route rendering query.html

---

### L2-U-003: Citation Side Panel [P2]

**Stream**: UI
**Files**: `app/ui/templates/partials/citation.html`
**Dependencies**: L2-U-002
**Interfaces**: Citation detail panel

**Acceptance Criteria**:
- [x] Create citation.html partial template
- [x] Display: document title, section path, page number
- [x] Show full paragraph text
- [x] Link to original document (if available)
- [x] Close button
- [x] Slide-in animation via CSS
- [x] htmx endpoint to fetch citation details

---

### L2-U-004: Feedback Form [P2]

**Stream**: UI
**Files**: `app/ui/templates/partials/feedback.html`
**Dependencies**: L2-U-002, L2-F-002
**Interfaces**: Feedback submission form

**Acceptance Criteria**:
- [x] Create feedback.html partial
- [x] Thumbs up/down buttons
- [x] Category dropdown (wrong_answer, incomplete, bad_citation, other)
- [x] Optional details textarea
- [x] htmx POST to /api/query/{id}/feedback
- [x] Success confirmation display
- [x] Form resets after submission

---

## Level 3: Integration Tests & Polish

**Estimated Time:** 1-2 weeks per stream
**Required Before:** Production deployment
**Agent Count:** 3 (parallel work)

---

## Stream: INTEGRATION TESTS

**Status Update (2026-02-22):**
- [x] Integration test suite passing (`36/36`)
- [x] Command verified: `ANTHROPIC_API_KEY=test-key ./.venv/bin/pytest tests/integration -q -p no:cacheprovider`
- [x] File breakdown: `test_api.py` 12/12, `test_evaluation.py` 2/2, `test_ingestion.py` 6/6, `test_orchestrator.py` 8/8, `test_sse.py` 8/8

### L3-T-001: Ingestion Pipeline Tests [P1]

**Stream**: Tests
**Files**: `tests/integration/test_ingestion.py`
**Dependencies**: L2-P-001, L1-T-002
**Interfaces**: Full pipeline integration tests

**Acceptance Criteria**:
- [x] Test: ingest test_policy.md end-to-end
- [x] Verify: document created in database
- [x] Verify: correct section count and hierarchy
- [x] Verify: paragraphs have correct para_ids
- [x] Verify: ToC JSON structure
- [x] Test: checkpoint recovery after simulated failure
- [x] Test: re-ingestion with same file_hash (dedup)
- [x] Use real Docling (no mocks) for parser tests

---

### L3-T-002: Orchestrator Tests [P1]

**Stream**: Tests
**Files**: `tests/integration/test_orchestrator.py`
**Dependencies**: L2-O-002, L1-T-003
**Interfaces**: Reasoning loop integration tests

**Acceptance Criteria**:
- [x] Test: simple factual query with mocked Anthropic
- [x] Verify: tool calls executed in correct order
- [x] Verify: evidence log populated
- [x] Verify: citations verified
- [x] Verify: confidence calculated correctly
- [x] Test: max iterations handling
- [x] Test: timeout handling
- [x] Test: cross-reference following

---

### L3-T-003: API Endpoint Tests [P1]

**Stream**: Tests
**Files**: `tests/integration/test_api.py`
**Dependencies**: L2-F-002, L2-F-003
**Interfaces**: HTTP endpoint tests

**Acceptance Criteria**:
- [x] Test: POST /api/documents/upload with valid PDF
- [x] Test: GET /api/documents returns list
- [x] Test: GET /api/documents/{id} returns document
- [x] Test: DELETE /api/documents/{id} removes document
- [x] Test: POST /api/query returns query_id
- [x] Test: POST /api/query with invalid input returns 400
- [x] Test: POST /api/query/{id}/feedback stores feedback
- [x] Use httpx AsyncClient for all tests

---

### L3-T-004: SSE Streaming Tests [P1]

**Stream**: Tests
**Files**: `tests/integration/test_sse.py`
**Dependencies**: L2-F-002
**Interfaces**: SSE event stream tests

**Acceptance Criteria**:
- [x] Test: SSE connection established
- [x] Test: progress events received during processing
- [x] Test: answer event received at end
- [x] Test: error event on failure
- [x] Test: connection closes after answer
- [x] Verify: event format matches schema
- [x] Use httpx with SSE support or manual parsing

---

### L3-T-005: 10-Question Evaluation [P1]

**Stream**: Tests
**Files**: `tests/integration/test_evaluation.py`
**Dependencies**: L1-T-006, L2-O-002
**Interfaces**: End-to-end question answering tests

**Acceptance Criteria**:
- [x] Run all 10 test questions from fixtures
- [x] For each: verify answer contains expected keywords
- [x] For each: verify citations reference expected sources
- [x] For each: verify confidence level appropriate
- [x] Generate evaluation report: pass/fail per question
- [x] Calculate metrics: answer accuracy, citation accuracy
- [x] Save results for trend analysis

---

## Stream: EVALUATION SUITE (Phase 3)

### L3-E-001: Expand Test Suite to 50 Questions [P3]

**Stream**: Evaluation
**Files**: `tests/fixtures/test_questions.py`
**Dependencies**: L3-T-005
**Interfaces**: Expanded evaluation dataset

**Acceptance Criteria**:
- [ ] 15 factual lookup (single doc)
- [ ] 10 factual lookup (specific section)
- [ ] 8 synthesis (single doc)
- [ ] 7 synthesis (cross-doc)
- [ ] 5 cross-reference following
- [ ] 5 unanswerable questions
- [ ] Each with expected_source, expected_keywords, category
- [ ] Cover all 4 languages (DE, FR, IT, EN)

---

### L3-E-002: Automated Evaluation Pipeline [P3]

**Stream**: Evaluation
**Files**: `scripts/run_evaluation.py`
**Dependencies**: L3-E-001, L2-O-002
**Interfaces**: CLI evaluation runner

**Acceptance Criteria**:
- [ ] Create runnable script: `python scripts/run_evaluation.py`
- [ ] Load test questions from fixtures
- [ ] Run each question through orchestrator
- [ ] Compare answers to expected (keyword matching)
- [ ] Verify citations exist and are accurate
- [ ] Calculate metrics: accuracy, citation_accuracy, avg_iterations, avg_latency
- [ ] Save results to `data/evaluation_runs/` with timestamp
- [ ] Print summary report

---

### L3-E-003: Evaluation Metrics Dashboard [P3]

**Stream**: Evaluation
**Files**: `app/api/routes/admin.py`, `app/ui/templates/admin/evaluation.html`
**Dependencies**: L3-E-002
**Interfaces**: Admin view for evaluation results

**Acceptance Criteria**:
- [ ] Add `GET /admin/evaluation` route
- [ ] List past evaluation runs with timestamps
- [ ] Show metrics per run: accuracy, citation_accuracy, etc.
- [ ] Drill-down to individual question results
- [ ] Trend chart showing accuracy over time
- [ ] Compare runs side-by-side

---

### L3-E-004: Confidence Scoring Calibration [P3]

**Stream**: Evaluation
**Files**: `app/core/evidence.py`
**Dependencies**: L3-E-001, L1-C-004
**Interfaces**: Improved confidence calculation

**Acceptance Criteria**:
- [ ] Analyze evaluation results to calibrate confidence thresholds
- [ ] Add metrics: evidence diversity (unique docs cited), evidence depth (avg para per source)
- [ ] Consider: unanswered cross-references reduce confidence
- [ ] Consider: single-source answers get medium max
- [ ] Document calibration reasoning in code comments
- [ ] Verify high-confidence answers are >90% accurate

---

## Stream: ADMIN PANEL (Phase 3)

### L3-A-001: Document Management UI [P3]

**Stream**: Admin
**Files**: `app/ui/templates/admin/documents.html`
**Dependencies**: L2-U-001, L2-F-003
**Interfaces**: Admin document management page

**Acceptance Criteria**:
- [ ] List all documents with metadata
- [ ] Upload form with drag-and-drop
- [ ] Delete button with confirmation modal
- [ ] Show ingestion status for each document
- [ ] Show unresolved cross-references count
- [ ] Filter by language
- [ ] Search by title

---

### L3-A-002: Cache Statistics Dashboard [P3]

**Stream**: Admin
**Files**: `app/ui/templates/admin/cache.html`, `app/api/routes/admin.py`
**Dependencies**: L2-U-001, L1-S-008
**Interfaces**: Cache monitoring page

**Acceptance Criteria**:
- [ ] Display cache hit rates for L1-L5
- [ ] Show cache sizes (entry counts)
- [ ] Manual cache invalidation buttons
- [ ] Dry-run mode toggle (use only cached results)
- [ ] Cache TTL configuration (display current values)
- [ ] Refresh button for live stats

---

### L3-A-003: Query Log Viewer [P3]

**Stream**: Admin
**Files**: `app/ui/templates/admin/queries.html`
**Dependencies**: L2-U-001, L1-S-003
**Interfaces**: Query history page

**Acceptance Criteria**:
- [ ] List recent queries with: timestamp, text (truncated), latency, cache_hit, confidence
- [ ] Filter by: date range, cache hit, confidence level
- [ ] Click to expand: full query text, sections explored
- [ ] Link to reasoning trace viewer
- [ ] Export to CSV

---

### L3-A-004: Reasoning Trace Viewer [P3]

**Stream**: Admin
**Files**: `app/ui/templates/admin/trace.html`
**Dependencies**: L2-U-001, L1-S-003
**Interfaces**: Chat-like trace visualization

**Acceptance Criteria**:
- [ ] Display trace as conversation: user → assistant → tool_call → tool_result → ...
- [ ] Syntax highlighting for JSON tool inputs/outputs
- [ ] Collapsible tool results (expand to see full content)
- [ ] Timeline view showing iteration timing
- [ ] Final answer with citation highlighting
- [ ] Link back to query in query log

---

### L3-A-005: Runtime Configuration [P3]

**Stream**: Admin
**Files**: `app/ui/templates/admin/config.html`, `app/api/routes/admin.py`
**Dependencies**: L2-U-001, L0-003
**Interfaces**: Runtime settings management

**Acceptance Criteria**:
- [ ] Display current settings: max_iterations, query_timeout, log_level
- [ ] Edit form for runtime-configurable values
- [ ] Validation before save
- [ ] Apply changes without restart (where possible)
- [ ] Show which settings require restart
- [ ] Audit log of configuration changes

---

## Task Summary by Phase

### Phase 1 (MVP) — 47 tasks

| Level | Stream | Tasks | Count |
|-------|--------|-------|-------|
| L0 | Foundation | L0-001 to L0-003 | 3 |
| L1 | Storage | L1-S-001 to L1-S-008 (excl P2) | 7 |
| L1 | Ingestion | L1-I-001 to L1-I-007 | 7 |
| L1 | Core | L1-C-001 to L1-C-006 | 6 |
| L1 | API | L1-A-001 to L1-A-005 | 5 |
| L1 | Tests | L1-T-001 to L1-T-006 | 6 |
| L1 | Scripts | L1-X-001 to L1-X-005 | 5 |
| L2 | Orchestrator | L2-O-001 to L2-O-003 | 3 |
| L2 | Pipeline | L2-P-001 to L2-P-002 | 2 |
| L2 | FastAPI | L2-F-001 to L2-F-005 | 5 |
| L3 | Tests | L3-T-001 to L3-T-005 | 5 |

### Phase 2 (Multi-Document) — 9 tasks

| Level | Stream | Tasks | Count |
|-------|--------|-------|-------|
| L1 | Storage | L1-S-004 | 1 |
| L1 | Ingestion | L1-I-008 | 1 |
| L2 | Orchestrator | L2-O-004 | 1 |
| L2 | Pipeline | L2-P-003 | 1 |
| L2 | UI | L2-U-001 to L2-U-004 | 4 |
| L1 | API | L1-A-006 | 1 |

### Phase 3 (Production) — 9 tasks

| Level | Stream | Tasks | Count |
|-------|--------|-------|-------|
| L3 | Evaluation | L3-E-001 to L3-E-004 | 4 |
| L3 | Admin | L3-A-001 to L3-A-005 | 5 |

---

## Quick Start Guide

### For Agent 1 (Storage)

```bash
# Start with these tasks in order:
# L0-001, L0-002, L0-003 (if not done)
# Then L1-S-001 → L1-S-002 → L1-S-003 → L1-S-005 → L1-S-006 → L1-S-007 → L1-S-008
```

### For Agent 2 (Ingestion)

```bash
# Wait for L0 completion, then:
# L1-I-001 → L1-I-002 → L1-I-003 → L1-I-004 → L1-I-005 → L1-I-006 → L1-I-007
```

### For Agent 3 (Core)

```bash
# Wait for L0 completion, then:
# L1-C-001 → L1-C-002 → L1-C-003 → L1-C-004 → L1-C-005 → L1-C-006
```

### For Agent 4 (API)

```bash
# Wait for L0 completion, then:
# L1-A-001 → L1-A-002 → L1-A-003 → L1-A-004 → L1-A-005
```

### For Agent 5 (Tests)

```bash
# Wait for L0 completion, then:
# L1-T-001 → L1-T-002 → L1-T-003 → L1-T-004 → L1-T-005 → L1-T-006
```

### For Agent 6 (Scripts)

```bash
# Wait for L0 completion, then:
# L1-X-001 → L1-X-002 → L1-X-003 → L1-X-004 → L1-X-005
```

---

## Verification Checklist

After all tasks complete, verify:

- [ ] All 6 Level 1 streams have balanced task counts (5-8 tasks each)
- [ ] No circular dependencies exist (all arrows point down in diagram)
- [ ] All files from plan.md Section 1 are covered by tasks
- [ ] All tools from plan.md Section 7 are implemented
- [ ] All API endpoints from plan.md Section 11 are implemented
- [ ] All database models from plan.md Section 3 are created
- [ ] Phase tags cover all deliverables from plan.md Sections 4-6
- [ ] Tests exist for all critical paths
