# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reasoning-RAG is a reasoning-driven document QA system for Caritas Switzerland that replaces traditional vector-similarity retrieval with an iterative, structure-aware reasoning loop. The core insight: **don't search for similar text — reason about where to look.**

**Status:** Implemented (ingestion, orchestrator, FastAPI + htmx UI under `app/`); `plan/plan.md` remains the architecture specification.

## Architecture

### Core Components

1. **Ingestion Pipeline**: Docling converts PDF/DOCX/PPTX → Markdown with heading hierarchy preservation. Best-effort structure analysis (accept imperfect heading detection). Haiku annotation for variable-length summaries, language detection, and cross-reference extraction
2. **Reasoning Orchestrator**: Single Claude Sonnet agent with 7 tools navigates document structure iteratively (max 8 iterations per query). Maintains evidence log and tracks visited sections
3. **Document Store**: SQLite for all structured data (documents, sections, paragraphs, cross-references, caches, traces). Filesystem for original files and parsed Markdown. In-memory ToC corpus
4. **FastAPI Backend**: RESTful API endpoints, SSE streaming for progress indicators and answers, document management, admin interface
5. **Web Frontend**: Plain HTML + htmx (server-rendered with progressive enhancement). Question input, streaming answers, citation side-panel, document links, feedback form

### Key Design Decisions

- **Single orchestrator over multi-agent**: Lower complexity, better observability, sufficient for ~20 document corpus
- **Structural navigation over vector search**: ToC-based reasoning knows where to look; embeddings are fallback only
- **SQLite over cloud DB**: Appropriate for scale, no infrastructure overhead, local deployment

### Tool Registry (7 Tools)

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `list_documents` | optional: topic/keyword, language filter | List of {doc_id, title, summary, language} | Discover available documents |
| `get_toc` | doc_id | Full ToC JSON tree | Navigate document structure |
| `read_section` | doc_id, node_id | All paragraphs in section with para_ids | Read actual section content |
| `read_paragraphs` | list of para_ids | Paragraph texts with full metadata | Targeted re-reading |
| `grep_documents` | query_text, optional doc_ids, optional regex | Matching paragraphs with para_ids | Cross-reference resolution and text search |
| `search_fallback` | query_text, optional doc_ids | Top-k paragraphs by embedding similarity | Embedding-based fallback (Phase 2) |
| `record_evidence` | para_id, relevance_note | Confirmation | Track evidence during reasoning loop |

**Key:** `grep_documents` is critical for cross-reference handling — it enables resolving references like "see Appendix G" or "gemäss Richtlinie Y" with full regex support and cross-document search

## Technology Stack

- **Python 3.12** (configured in pyproject.toml)
- **Document parsing**: Docling (unified PDF/DOCX/PPTX → Markdown)
- **LLM reasoning**: Claude Sonnet 4.6 (via Anthropic SDK; configured in `app/config.py`)
- **LLM preprocessing**: Claude Haiku 4.5 (section summaries, annotations, language detection; configured in `app/config.py`)
- **Backend**: FastAPI with SSE streaming
- **Storage**: SQLite + filesystem
- **Frontend**: Plain HTML + htmx (server-rendered with progressive enhancement)
- **Optional embeddings**: sentence-transformers + FAISS (Phase 2 fallback only)
- **Authentication**: None (local deployment, no access control needed)

## Development Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run FastAPI server
uvicorn app.main:app --reload

# Run tests
pytest tests/
```

## Implementation Roadmap

**Phase 1 (MVP)**: Single-document factual QA — Docling PDF parsing, ToC generation (Haiku-assisted summaries), reasoning loop with 4 core tools (`get_toc`, `read_section`, `read_paragraphs`, `grep_documents`), checkpoint-based ingestion recovery, basic FastAPI endpoint with SSE progress indicators

**Phase 2**: Multi-document reasoning, full tool set (`list_documents`, `search_fallback`, `record_evidence`), cross-reference detection and index, evidence verification, gap reporting, plain HTML + htmx web UI, DOCX/PPTX support, detailed user feedback form

**Phase 3**: Production readiness — all 5 cache layers (L1 ingestion cache through L5 reasoning trace cache), query logging and analytics, admin panel (document management, cache stats, timeout config, dry-run mode), full evaluation suite (50 test cases), confidence scoring, contradiction formatting, soft rate limiting

## Key Files

- `plan/plan.md` — Complete 1000+ line architecture specification (required reading before implementation)
- `pyproject.toml` — Python project configuration

## Data Model

**Paragraph ID format**: `{doc_id}:{section_id}:{para_index}` (e.g., `doc_policy_ict_2025:s001.1:p002`)

**ToC node structure**:
```json
{
  "node_id": "s001.1",
  "title": "Section Title",
  "summary": "LLM-generated 1-2 sentence summary",
  "page_range": [2, 3],
  "paragraph_count": 4,
  "cross_references": ["doc_other:s003.2"],
  "sub_nodes": []
}
```

## Reasoning Workflow

The orchestrator follows an **iterative reasoning loop** (max 8 iterations per query):

1. **Query Interpretation** - Parse user question, identify target documents/topics, detect language
2. **Document Discovery** - Use `list_documents` to identify candidate documents, load their ToCs
3. **Section Selection** - LLM reads pre-loaded ToCs, selects most promising unvisited sections
4. **Content Extraction** - Call `read_section` to read actual content
5. **Cross-Reference Handling** - If text contains references, use `grep_documents` to resolve them
6. **Evidence Evaluation** - Does this content answer the question fully, partially, or insufficiently?
7. **Loop or Synthesize** - If insufficient, continue loop; if sufficient (or max iterations reached), synthesize answer

**Key features:**
- Evidence log tracking (`record_evidence`) throughout loop
- Visited section tracking to avoid re-reading
- Unresolved references trigger inline warnings in answer
- 8-iteration limit bounds cost to ~$0.05-$0.15 per query

## Caching Strategy

**5-layer cache architecture** (deferred to Phase 3):

- **L1: Ingestion Cache** - Docling output, parsed structure (keyed by file_hash, TTL: until re-upload)
- **L2: ToC Corpus Cache** - Combined ToC JSON for all documents (in-memory, TTL: until any doc changes)
- **L3: Embedding Cache** - para_id → embedding vectors (SQLite + FAISS, Phase 2)
- **L4: Query Result Cache** - Query hash → answer + citations (SQLite, TTL: until referenced doc changes)
- **L5: Reasoning Trace Cache** - query_id → full tool call sequence (SQLite, forever retention for audit)

**Cache invalidation:** Document-level granularity. Re-uploading or deleting a document invalidates L1, L2, L3 (that doc), L4 (all queries citing that doc).

## Citation & Evidence Tracking

**End-to-end provenance chain:**

- Parsing creates stable para_ids: `{doc_id}:{section_id}:{para_index}`
- Retrieval operations return para_ids + page numbers + section path
- Reasoning loop calls `record_evidence(para_id, note)` to build evidence log
- Answer synthesis includes inline citations: `[Doc Title, Section X.Y, p.N]`
- Post-generation verification: every citation must exist in evidence log (regenerate answer if not)

**Three safeguards against hallucinated citations:**
1. LLM can only cite para_ids it has actually retrieved
2. Post-generation verification step
3. Quote-matching for direct quotes (fuzzy match for minor LLM paraphrasing)

## Guardrails & Security

- Max 8 reasoning iterations per query
- 60 second timeout per query (configurable in admin UI)
- All citations must trace to retrieved `para_id` in evidence log
- Document content delimited in `<document_content>` tags (prompt injection defense)
- Prompt injection: internal staff documents are trusted; no sanitization, but defense-in-depth via tagging and system instructions
- Access control: None (local deployment, all users see all documents)
- Audit logging: All queries logged forever; reasoning traces retained forever for compliance
- Data residency: All processing local; Anthropic API only receives document excerpts, never full documents