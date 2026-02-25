# Reasoning-RAG

A reasoning-driven document QA system that replaces traditional vector-similarity retrieval with an iterative, structure-aware reasoning loop. Built for Caritas Switzerland to answer questions over internal policy, regulation, and research documents in German, French, Italian, and English.

**Core insight:** don't search for similar text — reason about where to look.

---

## What Is Different From Conventional RAG

| Topic | Conventional RAG | Reasoning-RAG |
|---|---|---|
| Retrieval strategy | Single-shot similarity search (vector/keyword) | Iterative tool-driven navigation over document structure |
| Context construction | Top-k chunks, often flat | Section-aware reads, cross-reference following, fallback semantic search |
| Evidence discipline | Usually prompt-level citation instructions | Explicit `record_evidence` tool + post-generation citation verification |
| Explainability | Limited to retrieved chunks | SSE progress stream + evidence log + confidence statement |
| Operations | Often retrieval-only APIs | Admin pages for documents, cache controls, queries, trace view, evaluation |
| Cross-reference handling | Not handled | `grep_documents` resolves references like "see Appendix G" or "gemäss Richtlinie Y" |

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Browser / Client                          │
│           HTML + htmx          │          REST / SSE API            │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                        FastAPI Application                          │
│  ┌─────────────┐  ┌───────────────┐  ┌──────────┐  ┌───────────┐  │
│  │  /api/query │  │ /api/documents│  │ /admin/* │  │   /ui     │  │
│  └──────┬──────┘  └───────┬───────┘  └────┬─────┘  └─────┬─────┘  │
│         │                 │               │               │         │
│  ┌──────▼──────────────────────────────────────────────┐  │         │
│  │              Reasoning Orchestrator                  │  │         │
│  │  ┌──────────────────────────────────────────────┐   │  │         │
│  │  │  Iterative Loop (max 8 iterations)           │   │  │         │
│  │  │  Claude Sonnet 4.6 ←──── 7 Tools ──────────► │   │  │         │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐  │   │  │         │
│  │  │  │ get_toc  │ │read_sect │ │grep_documents│  │   │  │         │
│  │  │  └──────────┘ └──────────┘ └──────────────┘  │   │  │         │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐  │   │  │         │
│  │  │  │list_docs │ │read_paras│ │search_fallbk │  │   │  │         │
│  │  │  └──────────┘ └──────────┘ └──────────────┘  │   │  │         │
│  │  │  ┌────────────────────┐                       │   │  │         │
│  │  │  │  record_evidence   │   Evidence Log        │   │  │         │
│  │  │  └────────────────────┘   Visited Sections    │   │  │         │
│  │  └──────────────────────────────────────────────┘   │  │         │
│  └─────────────────────────────────────────────────────┘  │         │
│                                                            │         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     Storage Layer                             │  │
│  │  SQLite (documents, sections, paragraphs, caches, traces)     │  │
│  │  Filesystem (original files, parsed Markdown)                 │  │
│  │  In-memory (ToC corpus cache)                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                      Ingestion Pipeline                             │
│  File Upload → Docling Parser → Structure Analyzer →                │
│  Paragraph Extractor → Haiku Annotator → Cross-Ref Extractor →      │
│  SQLite + Filesystem                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Map

```
app/
├── main.py                    # FastAPI app, lifespan, middleware, route registration
├── config.py                  # Pydantic settings (loaded from .env)
├── dependencies.py            # Dependency injection (db session, orchestrator)
├── logging_config.py          # Structured logging setup
│
├── api/
│   ├── schemas.py             # Pydantic request/response models
│   ├── exceptions.py          # Custom exceptions (IngestionError, QueryTimeoutError, …)
│   ├── document_files.py      # Upload file validation and storage utilities
│   └── routes/
│       ├── query.py           # POST /api/query  |  GET /api/query/{id}/stream  |  POST /api/query/{id}/feedback
│       ├── documents.py       # POST/GET/DELETE /api/documents
│       ├── admin.py           # /admin/* endpoints (cache, queries, config, traces, evaluation)
│       └── ui.py              # /ui  /ui/admin  (Jinja template rendering)
│
├── core/
│   ├── orchestrator.py        # ReasoningOrchestrator — iterative loop + SSE streaming
│   ├── tools.py               # 7 tool schemas (Anthropic format) + ToolHandler execution
│   ├── prompts.py             # System prompt template with reasoning protocol
│   └── evidence.py            # EvidenceVerifier — citation extraction + verification
│
├── ingestion/
│   ├── pipeline.py            # IngestionPipeline — 6-stage coordinator with checkpoints
│   ├── docling_parser.py      # Docling wrapper: PDF/DOCX/PPTX → Markdown
│   ├── structure.py           # MarkdownStructureAnalyzer + ParagraphExtractor
│   ├── annotator.py           # HaikuAnnotator — summaries, language, cross-refs via Haiku
│   ├── cross_references.py    # CrossReferenceExtractor — pattern matching + indexing
│   └── checkpoints.py         # CheckpointManager — resumable ingestion via SQLite stages
│
├── storage/
│   ├── database.py            # Async SQLite engine + session factory + init_db()
│   ├── models.py              # 10 SQLAlchemy ORM models
│   ├── repositories.py        # DocumentRepository, ParagraphRepository, CrossReferenceRepository
│   ├── cache.py               # 5-layer cache (L1 ingestion → L5 reasoning traces)
│   └── embeddings.py          # EmbeddingSearch — FAISS similarity fallback (Phase 2)
│
└── ui/
    ├── static/css/styles.css
    ├── static/js/htmx.min.js
    └── templates/
        ├── base.html  query.html  citation.html  source_passage.html  feedback.html
        └── admin/  documents.html  queries.html  cache.html  config.html  trace.html  evaluation.html

scripts/
├── init_db.py                 # Database initialization
├── seed_test_data.py          # Load fixture documents
├── run_evaluation.py          # Evaluation harness (50-question suite)
└── verify_core_tasks.py       # Smoke-test core functionality

tests/
├── conftest.py                # Pytest fixtures (async client, test DB)
├── unit/                      # Unit tests
└── integration/
    ├── test_ingestion.py      test_orchestrator.py  test_api.py
    ├── test_sse.py            test_phase2.py        test_phase3.py
    └── test_evaluation.py
```

### Data Model

**Paragraph ID format:** `{doc_id}:{section_id}:{para_index}`
Example: `doc_policy_ict_2025:s001.1:p002`

**10 database tables:**

| Table | Purpose |
|---|---|
| `document` | Uploaded files — title, file_type, language, pages, file_hash, ToC JSON, summary |
| `section` | ToC node hierarchy — parent_section_id, heading_level, section_path |
| `paragraph` | Paragraph text with stable para_id, page number, section path |
| `cross_reference` | Extracted cross-references — source_para_id, target_doc_id, target_node_id, resolved |
| `query_cache` (L4) | Cached answers — query_hash → answer + citations + evidence_log (TTL-based) |
| `reasoning_trace` (L5) | Full tool call sequences — retained forever for audit and compliance |
| `query_log` | Analytics — query text, status, latency_ms, iterations, confidence, cache_hit |
| `user_feedback` | Per-query ratings and comments |
| `embedding` | para_id → vector (Phase 2, FAISS + SQLite) |
| `ingestion_checkpoint` | Per-document stage progress for resumable ingestion |

**ToC node JSON structure:**
```json
{
  "node_id": "s001.1",
  "title": "Section Title",
  "summary": "LLM-generated 1–2 sentence summary",
  "page_range": [2, 3],
  "paragraph_count": 4,
  "cross_references": ["doc_other:s003.2"],
  "sub_nodes": []
}
```

---

## How Reasoning RAG Works — Step by Step

### Pipeline 1: Document Ingestion

When a document is uploaded, it passes through a six-stage pipeline managed by `IngestionPipeline` (`app/ingestion/pipeline.py`). Each stage writes a checkpoint to SQLite so ingestion can resume from the last successful stage on failure.

```
Upload → [Stage 1] Parse → [Stage 2] Analyze Structure → [Stage 3] Extract Paragraphs
       → [Stage 4] Annotate → [Stage 5] Extract Cross-References → [Stage 6] Save to DB
```

**Stage 1 — Parse (`DoclingParser`)**

- File hash is computed. If it matches an existing record (L1 cache), the pipeline is skipped — the document is already ingested.
- Docling converts `.pdf`, `.docx`, or `.pptx` to Markdown, preserving heading hierarchy (`#`, `##`, `###`).
- Best-effort: imperfect heading detection is accepted rather than rejected.
- Output: raw Markdown string + page boundary metadata.

**Stage 2 — Analyze Structure (`MarkdownStructureAnalyzer`)**

- Markdown is parsed into a tree of headings.
- Each heading node gets a stable `section_id` based on its depth and positional index (e.g., `s001.1`).
- The full ToC JSON tree is assembled.
- Output: ordered list of `Section` objects with parent/child relationships.

**Stage 3 — Extract Paragraphs (`ParagraphExtractor`)**

- Each section's content is split into individual paragraphs.
- Every paragraph receives a stable `para_id`: `{doc_id}:{section_id}:{para_index}` (e.g., `doc_hr_policy:s002.3:p001`).
- Page number is derived from Docling's page boundary data.
- Output: flat list of `Paragraph` objects with full metadata.

**Stage 4 — Annotate (`HaikuAnnotator`)**

Claude Haiku 4.5 is called once per section to produce:
- A 1–2 sentence summary stored on the ToC node.
- Document-level language detection (`de`, `fr`, `it`, `en`).
- Cross-reference signals (phrases that likely reference other sections or documents).

Haiku is used here (not Sonnet) to keep annotation cost low across many sections.

**Stage 5 — Extract Cross-References (`CrossReferenceExtractor`)**

- Pattern matching (regex) over paragraph text finds phrases like:
  - "see Section 4.3", "vgl. Anhang B", "gemäss Richtlinie Y", "refer to [Document]"
- Each match creates an unresolved `CrossReference` record: `{source_para_id, source_text, target_doc_id, target_node_id, resolved: false}`.
- References are resolved at query time by `grep_documents`.

**Stage 6 — Save (`DocumentRepository`, `ParagraphRepository`)**

- All ORM objects are bulk-written to SQLite.
- The ToC JSON is serialized and stored on the `Document` row.
- On completion, the in-memory ToC corpus cache (L2) is invalidated so the new document appears immediately.
- Original file is kept on the filesystem under `./documents/{doc_id}/`.

---

### Pipeline 2: Query & Reasoning Loop

A user question triggers the following flow across two HTTP requests.

#### Step 1 — Submit Query (`POST /api/query`)

```
Client → POST /api/query  { "question": "...", "doc_ids": [...] }
       ← { "query_id": "...", "stream_url": "/api/query/{id}/stream" }
```

- Input is validated by `QueryRequest` schema.
- A query hash is computed. If an L4 cache hit exists (same question + doc scope, within TTL), the cached answer is returned immediately without running the orchestrator.
- Otherwise, the query is logged to `QueryLog` with status `pending` and a `query_id` is returned together with the SSE stream URL.

#### Step 2 — Stream Execution (`GET /api/query/{id}/stream`)

The client connects to the SSE stream. The orchestrator starts executing and emits real-time events.

```
Client → GET /api/query/{id}/stream
       ← event: progress  {"iteration": 1, "tool": "get_toc", "status": "called"}
       ← event: progress  {"iteration": 1, "tool": "read_section", "status": "called"}
       ← event: progress  {"iteration": 2, "tool": "grep_documents", "status": "called"}
       ← event: answer    {"answer": "...", "citations": [...], "confidence": "high", ...}
```

#### Step 3 — Reasoning Loop (inside `ReasoningOrchestrator`)

The orchestrator calls Claude Sonnet 4.6 with:
- The **system prompt** (`app/core/prompts.py`) — includes the reasoning protocol, citation rules, cross-reference rules, and gap-reporting guidance.
- **Pre-loaded ToC corpus** — the full ToC JSON for all in-scope documents is injected into the system prompt, giving the model an overview of available content *before* the loop starts.
- **Tool definitions** — all 7 tools as Anthropic tool schemas.
- **Conversation history** — accumulates tool calls and results across iterations.

The loop runs until one of:
- The model stops calling tools (i.e., it has enough evidence).
- `record_evidence` is called and evidence is deemed sufficient.
- `max_iterations` (default: 8) is reached — a partial answer is synthesized.
- `query_timeout_seconds` (default: 60 s) elapses — `QueryTimeoutError` is raised.

**Model fallback:** If the configured `REASONING_MODEL` ID returns a 404 from the API (model unavailable), the orchestrator automatically retries with `claude-sonnet-4-6-latest` and then with hardcoded fallback IDs.

```
┌─────────────────────────────────────────────────────────────┐
│  Iteration N                                                │
│                                                             │
│  1. Claude reads system prompt + ToC corpus + history       │
│  2. Claude emits one or more tool_use blocks                │
│  3. ToolHandler dispatches each tool call:                  │
│     • get_toc        → returns full ToC JSON                │
│     • read_section   → returns paragraphs in section        │
│     • read_paragraphs→ returns targeted paragraph texts     │
│     • grep_documents → searches text/regex across docs      │
│     • list_documents → lists available docs with summaries  │
│     • search_fallback→ embedding similarity (Phase 2)       │
│     • record_evidence→ appends para_id to evidence log      │
│  4. Tool results are appended to conversation history       │
│  5. SSE progress event emitted                              │
│  6. Repeat until model stops calling tools                  │
│                                                             │
│  Post-loop:                                                 │
│  7. EvidenceVerifier extracts all citations from answer     │
│  8. Each citation is verified against evidence_log          │
│     (if citation not in log → regenerate answer)            │
│  9. Confidence is computed: high / medium / low             │
│  10. Result is emitted as SSE "answer" event                │
└─────────────────────────────────────────────────────────────┘
```

#### Step 4 — Tool Execution Detail (`ToolHandler`)

Each tool call hits the local SQLite database — no external calls except to the Anthropic API for the reasoning model itself.

| Tool | What it does internally |
|---|---|
| `list_documents` | Queries `DocumentRepository.list_documents(topic, language)`. Returns title, summary, language per document. |
| `get_toc` | Deserializes the `toc_json` column from the `Document` row. Returns the full nested ToC tree. |
| `read_section` | Calls `ParagraphRepository.get_by_section(doc_id, node_id)`. Returns ordered paragraphs with para_ids and page numbers. Marks section as visited to prevent re-reading. |
| `read_paragraphs` | Calls `ParagraphRepository.get_by_ids(para_ids)`. For targeted re-reading of specific paragraphs. |
| `grep_documents` | Calls `ParagraphRepository.search_text(query, doc_ids, regex)`. SQLite `LIKE` search; if `regex=true`, results are filtered via Python `re.compile`. Essential for resolving cross-references. |
| `search_fallback` | Calls `EmbeddingSearch.search(query_text, doc_ids, top_k)`. FAISS similarity search over stored embeddings (Phase 2). |
| `record_evidence` | Appends `{para_id, relevance_note, timestamp}` to the in-memory `evidence_log`. Returns current evidence count. |

#### Step 5 — Evidence Verification (`EvidenceVerifier`)

After the model produces its final answer:

1. All citation strings (`[Doc Title, Section X.Y, p.N]`) are extracted by regex from the answer text.
2. Each citation's `para_id` is checked against the `evidence_log` accumulated during the loop.
3. If any citation is not in the evidence log, the answer is flagged for regeneration (the model is called again with an explicit instruction to only cite what it actually read).
4. Direct quotes are fuzzy-matched against the original paragraph text.

**Three safeguards against hallucinated citations:**
- The model can only reference `para_id`s that `ToolHandler` has actually returned.
- Post-generation verification step above.
- Quote fuzzy-matching for direct quotes.

#### Step 6 — Confidence Scoring

Confidence is computed from:
- Number of iterations used (fewer = more direct answer = higher confidence).
- Number of evidence items recorded.
- Whether gaps were explicitly noted in the answer.
- Whether citations passed post-generation verification.

Output: `"high"`, `"medium"`, or `"low"` plus a human-readable `confidence_statement`.

#### Step 7 — Caching & Persistence

After a successful answer:
- **L4 cache:** Query hash → answer + citations + evidence_log is written to `QueryCache` with a TTL of `QUERY_CACHE_TTL_SECONDS` (default 24 h). Invalidated when any cited document changes.
- **L5 trace:** Full tool call sequence → `ReasoningTrace` with no TTL (retained forever for audit and compliance).
- `QueryLog` is updated with final status, latency_ms, iterations, and confidence.

---

### Pipeline 3: Cross-Reference Resolution

A key differentiator from conventional RAG: the system can follow references embedded in document text.

```
read_section returns paragraph:
  "For the expense policy, refer to Anhang B of the Finanzreglement."

Orchestrator detects reference pattern → calls grep_documents:
  grep_documents(query_text="Anhang B", doc_ids=["doc_finanzreglement"])

Returns matching paragraphs from the referenced section.
Evidence is recorded, citation is added to answer.
```

Unresolved references (target document not in corpus) are surfaced as inline warnings:
> Note: Referenced section "Anhang B" was not found in the available documents.

---

### Cache Architecture (5 Layers)

| Layer | Key | Storage | TTL | Purpose |
|---|---|---|---|---|
| **L1** | `file_hash` | `IngestionCheckpoint` table | Until re-upload | Skip re-parsing identical files |
| **L2** | global | In-memory dict | Until any doc changes | Fast ToC corpus access at query start |
| **L3** | `para_id` | `Embedding` table + FAISS index | Until doc changes | Embedding vectors (Phase 2) |
| **L4** | `query_hash` | `QueryCache` table | 86,400 s (configurable) | Skip full reasoning for repeated queries |
| **L5** | `query_id` | `ReasoningTrace` table | Forever | Audit log of every reasoning step |

---

## Technology Stack

| Component | Technology |
|---|---|
| Python | 3.12+ |
| Backend framework | FastAPI 0.115+ + Uvicorn |
| ORM / DB driver | SQLAlchemy 2.0 async + aiosqlite |
| Document parsing | Docling 2.15+ (unified PDF/DOCX/PPTX → Markdown) |
| LLM reasoning | Claude Sonnet 4.6 (`claude-sonnet-4-6`) via Anthropic SDK |
| LLM annotation | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) |
| Frontend | Plain HTML + htmx (server-rendered, progressive enhancement) |
| Streaming | Server-Sent Events (SSE) via `sse-starlette` |
| Templating | Jinja2 |
| Embeddings (Phase 2) | sentence-transformers 3.3+ + faiss-cpu 1.9+ |
| Config management | Pydantic-settings |
| Linting / typing | ruff + mypy (strict) |
| Testing | pytest + pytest-asyncio + httpx |

---

## Quick Start

### 1. Clone and set up environment

```bash
git clone <your-repo-url>
cd Reasoning-RAG
python3.12 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and set your Anthropic API key:

```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

All other defaults are production-ready for a local deployment.

### 3. Initialize the database

```bash
python scripts/init_db.py
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

Open in browser:
- **User interface:** `http://127.0.0.1:8000/ui`
- **Interactive API docs:** `http://127.0.0.1:8000/docs`
- **Admin — documents:** `http://127.0.0.1:8000/admin/documents`
- **Health check:** `http://127.0.0.1:8000/health`

### 5. First query walkthrough

1. Upload a document at `http://127.0.0.1:8000/admin/documents` (PDF, DOCX, or PPTX).
2. Wait for ingestion to complete — progress is shown inline.
3. Go to `http://127.0.0.1:8000/ui` and type a question.
4. Watch the live SSE progress events as the reasoning loop runs tool calls.
5. Read the answer with inline citations `[Document Title, Section X.Y, p.N]`.
6. Open the citation side-panel to inspect the source paragraph in context.
7. Submit feedback (thumbs up/down) via the feedback form.

---

## API Reference

### Query

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/query` | Submit a question. Returns `query_id` + `stream_url`. |
| `GET` | `/api/query/{query_id}/stream` | SSE stream — emits `progress` + `answer` events. |
| `POST` | `/api/query/{query_id}/feedback` | Submit rating and comment for a query. |

**POST /api/query — request body:**
```json
{
  "question": "What is the expense reimbursement limit?",
  "doc_ids": ["doc_hr_policy_2025"]
}
```

**SSE event types:**
```
event: progress
data: {"iteration": 1, "tool": "read_section", "status": "called"}

event: answer
data: {
  "answer": "The reimbursement limit is CHF 150 per day [HR Policy 2025, Section 4.2, p.12].",
  "confidence": "high",
  "confidence_statement": "...",
  "citations": [...],
  "sections_explored": 3,
  "iterations": 2,
  "latency_breakdown": {...}
}

event: error
data: {"error": "Query timed out after 60 seconds"}
```

### Documents

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload and ingest a document (multipart/form-data). |
| `GET` | `/api/documents` | List all documents with metadata. |
| `GET` | `/api/documents/{doc_id}` | Get document metadata and ToC. |
| `DELETE` | `/api/documents/{doc_id}` | Delete document and cascade all related data. |

### Admin

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/cache/stats` | L1–L5 cache sizes and L4 hit rate. |
| `POST` | `/api/admin/cache/invalidate` | Invalidate cache for a document or globally. |
| `GET` | `/api/admin/queries/recent` | Query log with filtering and CSV export. |
| `GET` | `/api/admin/traces/{query_id}` | Full reasoning trace for a query. |
| `GET` | `/api/admin/config` | Read runtime configuration. |
| `PUT` | `/api/admin/config` | Update runtime configuration (iterations, timeout, TTL…). |

---

## Configuration

All settings are read from environment variables (`.env` file). None require a server restart except `ANTHROPIC_API_KEY`.

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/reasoning_rag.db` | Async SQLite URL |
| `DOCUMENTS_PATH` | `./documents` | Filesystem path for uploaded originals |
| `REASONING_MODEL` | `claude-sonnet-4-6` | Model for reasoning loop (with automatic fallback) |
| `ANNOTATION_MODEL` | `claude-haiku-4-5-20251001` | Model for ingestion annotation |
| `MAX_REASONING_ITERATIONS` | `8` | Max tool-call iterations per query |
| `QUERY_TIMEOUT_SECONDS` | `60` | Hard timeout for reasoning loop |
| `INGESTION_TIMEOUT_SECONDS` | `300` | Hard timeout for document ingestion |
| `QUERY_CACHE_TTL_SECONDS` | `86400` | L4 query cache TTL (seconds) |
| `DRY_RUN_CACHE_ONLY` | `false` | If true, only serve cached answers — no LLM calls |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Admin & Observability

All admin pages are at `/admin/*`:

| Page | URL | What it shows |
|---|---|---|
| Documents | `/admin/documents` | Upload, list, and delete documents; ingestion status |
| Queries | `/admin/queries` | Query log with latency, confidence, cache hits; CSV export |
| Cache | `/admin/cache` | L1–L5 cache sizes and hit rates; manual invalidation |
| Trace viewer | `/admin/trace/{query_id}` | Full step-by-step tool call sequence for any query |
| Config | `/admin/config` | Live-edit runtime configuration |
| Evaluation | `/admin/evaluation` | Evaluation suite results dashboard |

---

## Development

```bash
# Run full test suite
pytest -q -p no:cacheprovider

# Integration tests only
pytest tests/integration -q -p no:cacheprovider

# Lint
ruff check app tests

# Type check
mypy app

# Seed test data
python scripts/seed_test_data.py

# Run evaluation pipeline (50 questions)
python scripts/run_evaluation.py

# Verify core functionality
python scripts/verify_core_tasks.py
```

### Adding a document format

1. Add a parser in `app/ingestion/docling_parser.py` (Docling supports most formats).
2. Register the MIME type in `app/api/document_files.py`.
3. Add integration tests under `tests/integration/test_ingestion.py`.

### Enabling embeddings (Phase 2)

```bash
pip install -e ".[embeddings]"
```

Sentence-transformers and FAISS are optional dependencies. Once installed, `search_fallback` will use real embedding similarity instead of returning an empty result.

---

## Project Structure

```
Reasoning-RAG/
├── app/                  # Application source
│   ├── api/              # HTTP routes + schemas + exceptions
│   ├── core/             # Orchestrator, tools, prompts, evidence
│   ├── ingestion/        # 6-stage ingestion pipeline
│   ├── storage/          # SQLAlchemy models, repositories, caches
│   └── ui/               # Jinja templates + static assets
├── tests/                # Pytest suite (unit + integration)
├── scripts/              # DB init, evaluation, seeding, type checks
├── plan/                 # Architecture spec, implementation plan, task list
├── data/                 # SQLite database (auto-created)
└── documents/            # Uploaded document storage (auto-created)
```

---

## Guardrails

- Max 8 reasoning iterations per query (bounds cost to ~$0.05–$0.15 per query).
- 60-second hard timeout per query (configurable).
- All citations must trace to a `para_id` in the evidence log — post-generation verification enforced.
- Document content is delimited in `<document_content>` tags in the system prompt (prompt injection defense).
- All queries and reasoning traces are logged forever for compliance.
- Data residency: all processing is local; Anthropic API receives only document excerpts, never full documents.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `model not found` | Check `REASONING_MODEL` / `ANNOTATION_MODEL` in `.env`. Valid IDs: `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. Restart server after change. |
| `401 invalid x-api-key` | Check `ANTHROPIC_API_KEY` in `.env` and reload the process. |
| SSE stream interrupts mid-answer | Check backend logs for timeout or exception. Hard-refresh browser after frontend updates. |
| Ingestion stuck | Check `ingestion_checkpoint` table for failed stage. Delete the checkpoint row and re-upload to restart from scratch. |
| Empty answer / low confidence | Document may not contain the answer, or the relevant section uses phrasing the model did not match. Try a more specific question or verify the document content via `/admin/documents`. |
| `search_fallback` returns nothing | Embeddings are a Phase 2 optional dependency. Install `pip install -e ".[embeddings]"` to enable. |