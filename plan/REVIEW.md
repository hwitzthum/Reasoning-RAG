# Code Review — Findings & Improvement Backlog

**Date:** 2026-02-24
**Scope:** Full codebase review across `app/core`, `app/ingestion`, `app/storage`, `app/api`
**Method:** Two-agent review — code quality/performance/security analysis + adversarial edge case analysis

---

## Tier 1 — Fix Before Any Real Usage

*These will cause data loss, silent failures, or scalability collapse.*

---

### T1-1 `search_text` loads entire paragraph table into Python memory

**Files:** `app/storage/repositories.py:243`
**Severity:** CRITICAL
**Confirmed by:** Both agents independently

`ParagraphRepository.search_text` executes `select(Paragraph)` with no WHERE clause on text, loads all rows into Python, then filters in a loop. For 20 documents × 500 paragraphs = 10,000 rows loaded per search call, repeated up to 8× per query. Causes memory exhaustion and O(n) Python-side scan at every `grep_documents` tool invocation.

The existing `ix_paragraphs_text_fts` index in `models.py` is a B-tree index — it does **not** accelerate `LIKE '%...%'` queries.

**Fix:**
- Push text filtering into SQL: `WHERE text LIKE '%query%'`
- For production: add an FTS5 virtual table with `CREATE VIRTUAL TABLE paragraphs_fts USING fts5(...)`
- Add a hard `LIMIT` clause regardless of approach
- Apply doc_id filtering before text filtering (already done at SQL level — keep this)

---

### T1-2 SQLite concurrent writes — `database is locked` under load

**Files:** `app/storage/database.py:11`, `app/ingestion/pipeline.py:738`
**Severity:** CRITICAL
**Confirmed by:** Both agents

Default SQLite journal mode allows only one writer at a time. Simultaneous ingestion jobs, or an ingestion + a streaming query, will produce intermittent `OperationalError: database is locked`. The async engine shares one connection pool across all requests.

**Fix:**
- Enable WAL mode at startup: `PRAGMA journal_mode=WAL`
- Set `connect_args={"timeout": 30}` on the engine
- Consider a dedicated write session vs. read sessions pattern

---

### T1-3 Checkpoint and pipeline transaction desync — data loss on recovery

**Files:** `app/ingestion/checkpoints.py:94`, `app/ingestion/pipeline.py:738`
**Severity:** HIGH

`CheckpointManager.save()` calls `db.commit()` after every stage. If `_save_to_database` then fails and rolls back, the checkpoint reports "stage=complete" but the document data was never persisted. On the next startup, the pipeline skips re-ingestion and considers the document done — it isn't.

Additionally, checkpoint resume does not re-verify the file hash. If the source file is modified or deleted between crash and resume, `_resume_from_checkpoint` silently ingests different content under the original checkpoint's `doc_id`.

**Fix:**
- Checkpoints must use a separate DB session, or be written inside the same transaction as the data they protect
- Write the final completion checkpoint within the same `commit()` as the paragraph bulk insert
- Store `file_hash` in the checkpoint and verify it matches before resuming; if mismatched, delete the checkpoint and restart

---

### T1-4 `doc_id` derived from filename with no sanitization

**Files:** `app/ingestion/pipeline.py:106`, `app/api/routes/documents.py:43`
**Severity:** HIGH
**Confirmed by:** Both agents

`doc_id` is derived from `file_path.stem` without sanitization. A filename like `../../../etc/passwd.pdf` produces a `doc_id` with path separators, which propagates into SQL LIKE patterns (`like(f"{doc_id}:%")`), filesystem paths, and the system prompt. LIKE wildcard characters (`%`, `_`) in filenames silently match unintended rows.

The `String(12)` column length in `models.py` also silently truncates doc_ids longer than 12 characters (SQLite won't enforce this, but other backends would).

**Fix:**
- Sanitize `doc_id` to `[a-z0-9_-]{1,64}` immediately after derivation
- Reject filenames that produce empty or colliding slugs
- Escape LIKE metacharacters in any `like()` pattern built from `doc_id`
- Change `String(12)` to `String(255)` on all `doc_id` columns

---

### T1-5 Malformed `toc_json` poisons all queries

**Files:** `app/core/orchestrator.py:467`
**Severity:** HIGH

If one document has a corrupt `toc_json` (partial write, encoding error, wrong type), `_format_toc_tree` crashes with `AttributeError` or `KeyError`. Since `_load_toc_corpus` loads all documents, one corrupt entry aborts the entire corpus load and crashes every query until the document is deleted and re-ingested.

**Fix:**
- Wrap each document's ToC formatting in a per-document `try/except`
- Log a warning and skip the corrupt document rather than propagating the exception
- Validate `toc_json` type at write time in `_save_to_database`

---

## Tier 2 — Fix Before Production Deployment

*Correctness issues, anti-hallucination bypasses, and significant performance gaps.*

---

### T2-1 Single-document citation verification bypass defeats anti-hallucination guarantee

**Files:** `app/core/evidence.py:198`
**Severity:** HIGH

`EvidenceVerifier` has a fallback: if only one source document exists in the evidence log, all citations are auto-verified regardless of whether the cited paragraph was actually read. This disables the primary hallucination safeguard for all single-document queries — the most common production use case.

**Fix:**
- Remove the blanket fallback entirely
- At minimum, require that the cited document title fuzzy-matches and that a `para_id` exists in the evidence log
- Log all cases where the fallback would have triggered, for monitoring

---

### T2-2 Prompt injection via document metadata in system prompt

**Files:** `app/core/orchestrator.py:173`, `app/core/prompts.py`
**Severity:** HIGH
**Confirmed by:** Both agents

Document titles, summaries, and section text are interpolated verbatim into the system prompt via Python's `.format()`. Two distinct bugs:

1. A document title containing `{variable}` causes a `KeyError` crash at query time
2. A document title with XML-breaking content (e.g., `</pre_loaded_tocs><role>New instructions...`) can break out of the `<pre_loaded_tocs>` block and inject instructions into the system prompt

**Fix:**
- Replace `.format(toc_corpus=...)` with `string.Template` substitution (dollar-sign syntax eliminates brace injection)
- XML-escape all document titles and summaries before interpolation
- Wrap each document's content in explicit XML delimiters in the prompt (`<document title="...">...</document>`)

---

### T2-3 Haiku annotation is sequential — ingestion is impractically slow

**Files:** `app/ingestion/pipeline.py:581`
**Severity:** HIGH

Sections are annotated one at a time. For a document with 50 sections at ~2 s/call, annotation alone takes ~100 seconds. This blocks document availability.

**Fix:**
- Use `asyncio.gather(*[annotate(node) for node in nodes])` with `asyncio.Semaphore(10)` to cap concurrency
- Target: reduce 100 s annotation to ~15 s with 10 concurrent Haiku calls

---

### T2-4 `record_evidence` makes 2–3 sequential DB round-trips per call

**Files:** `app/core/tools.py:409`
**Severity:** HIGH

Each `record_evidence` call triggers `get_by_ids([para_id])`, `get_by_id(paragraph.doc_id)`, and a direct `Section.title` lookup — three serial DB queries for metadata enrichment. In a reasoning loop with frequent evidence calls, this accumulates significant DB overhead.

**Fix:**
- Collect `{para_id, relevance_note}` pairs during the loop with no enrichment
- Enrich all evidence entries in a single batched JOIN query during answer synthesis

---

### T2-5 L2 ToC corpus cache is not actually caching anything

**Files:** `app/storage/cache.py:42`
**Severity:** HIGH
**Confirmed by:** Both agents

`CacheManager._toc_corpus_cache` is an instance variable. A new `CacheManager` is instantiated per request, so the cache is always empty on every request. The in-memory ToC corpus described in the architecture does not exist in practice — every query hits the DB.

**Fix:**
- Move `_toc_corpus_cache` to a module-level dict (or app-state singleton) with a version counter
- Invalidate on document upload, deletion, or re-ingestion
- This is a significant latency win — ToC loading currently incurs N DB queries per query

---

### T2-6 Synchronous Anthropic client blocks the event loop

**Files:** `app/core/orchestrator.py:404`, `app/core/evidence.py:460`
**Severity:** MEDIUM

The synchronous `Anthropic` client is wrapped in `asyncio.to_thread`. Under concurrent requests this exhausts the thread pool. The `AsyncAnthropic` client is available and natively async.

**Fix:**
- Replace `Anthropic` with `AsyncAnthropic` throughout
- All `client.messages.create(...)` calls become `await client.messages.create(...)`

---

### T2-7 DB session held open for entire SSE stream lifetime

**Files:** `app/api/routes/query.py:145`
**Severity:** HIGH

The `db` session injected into the query route handler is held for the entire SSE stream duration (up to 60 seconds). Each concurrent streaming query holds a SQLite connection, blocking writes from ingestion and other queries.

**Fix:**
- Open a short-lived session for discrete operations within the generator (query log update, cache write, trace persist) rather than holding one session for the full stream
- Use `async with AsyncSessionLocal() as session:` blocks scoped to individual DB operations

---

### T2-8 Client disconnect leaves query in "processing" state forever

**Files:** `app/api/routes/query.py:148`
**Severity:** HIGH

If the SSE client disconnects (browser tab closed, network drop), the `event_generator` coroutine may be cancelled without updating `query_log.status`. Zombie "processing" queries accumulate. The reasoning orchestrator also continues running, burning API cost with no client to receive the result.

**Fix:**
- Add a `finally` block in `event_generator` that unconditionally sets `query_log.status = "cancelled"` or `"completed"` and persists the trace on any exit path
- Handle `asyncio.CancelledError` explicitly (verify behavior under Python 3.12)
- Consider running the orchestrator as a cancellable `asyncio.Task` so cancellation propagates to in-flight API calls

---

### T2-9 `read_section` has no pagination — single section can return unbounded paragraphs

**Files:** `app/core/tools.py:278`
**Severity:** HIGH

A document with no headings produces a single root section containing all content. `read_section` returns all its paragraphs with no limit, potentially injecting megabytes of text into the Claude message history and exceeding the context window.

**Fix:**
- Limit `read_section` to return at most 50 paragraphs
- Add an `offset` parameter so the LLM can request subsequent pages
- Truncate individual paragraph texts at a configurable character limit (e.g., 2000 chars)

---

### T2-10 No rate limiting on query submission — unbounded API cost exposure

**Files:** `app/api/routes/query.py:74`
**Severity:** HIGH

The `/api/query` endpoint accepts unlimited submissions. Each query triggers up to 8 Claude Sonnet API calls. Worst-case cost estimate: ~$5.28 per query (1.6M input tokens + 32k output tokens at Sonnet pricing). A misconfigured or malicious client can trigger unbounded concurrent orchestrator instances.

**Fix:**
- Add rate limiting middleware (e.g., `slowapi`)
- Add a global concurrency semaphore limiting simultaneous orchestrator runs (e.g., 5)
- Add a per-query cost estimate and abort if projected cost exceeds a configurable threshold

---

### T2-11 Cache invalidation on document deletion is not implemented

**Files:** `app/api/routes/documents.py:291`, `app/storage/cache.py`
**Severity:** MEDIUM

The architecture specifies L4 cache invalidation when a document is deleted. The `CacheManager` has an `invalidate_for_document` method, but it is never called in the document deletion path. Stale cached answers with dead `para_id` citations accumulate indefinitely.

Additionally, `invalidate_for_document` loads the entire `QueryCache` table into memory to perform Python-side filtering — an O(n) memory spike on every deletion.

**Fix:**
- Call `cache_manager.invalidate_for_document(doc_id)` in the document deletion handler
- Add a `cited_doc_ids` column (JSON array) to `QueryCache` for indexed SQL-side filtering instead of loading all rows

---

### T2-12 `DRY_RUN_CACHE_ONLY` not enforced at stream endpoint

**Files:** `app/api/routes/query.py:140`
**Severity:** MEDIUM

`dry_run_cache_only` is checked at `POST /api/query` but not at `GET /api/query/{id}/stream`. If the flag is toggled on after a stream URL has been issued, the stream endpoint runs a full orchestrator anyway.

**Fix:**
- Check `settings.dry_run_cache_only` at the start of `event_generator`
- Return an error SSE event if no cache hit exists and dry-run mode is active

---

## Tier 3 — Robustness Improvements

*Real edge cases that will surface in normal usage.*

---

### T3-1 Tool call cycling — LLM loops on same section with no detection

**Files:** `app/core/orchestrator.py:178`
**Severity:** HIGH

The `visited_sections` set only tracks `read_section` calls. The LLM can call `grep_documents` or `get_toc` on the same content repeatedly across all 8 iterations, wasting the entire reasoning budget.

**Fix:**
- Track `(tool_name, canonical_input_hash)` across iterations
- After 2 identical calls, inject a correction message: "You have already tried this. Explore a different section or synthesize from current evidence."

---

### T3-2 LLM skips `record_evidence` — evidence log stays empty

**Files:** `app/core/orchestrator.py:492`
**Severity:** HIGH

If the model answers without calling `record_evidence`, the evidence log is empty. All citations fail post-generation verification, producing `confidence: "low"` with zero verified citations even when the answer is well-grounded in sections the model did read.

**Fix:**
- After each `read_section` or `read_paragraphs` call, auto-insert lightweight evidence entries for all returned `para_ids` (flagged `auto_recorded: true`) as a safety net
- If `evidence_log` is empty after the loop and the answer contains citations, flag the answer prominently as unverifiable

---

### T3-3 API failure mid-reasoning discards all gathered evidence

**Files:** `app/core/orchestrator.py:383`
**Severity:** MEDIUM

If the Anthropic API call fails on iteration 5, the exception propagates to the top-level `except` block and emits an error event. All evidence collected in iterations 1–4 is lost with no partial answer attempt.

**Fix:**
- Catch API errors inside the iteration loop
- If `evidence_log` is non-empty, call `_synthesize_partial_answer` before propagating the exception

---

### T3-4 Two clients streaming the same `query_id` simultaneously

**Files:** `app/api/routes/query.py:140`
**Severity:** MEDIUM

Nothing prevents two clients from connecting to the same `query_id/stream`. Both run full independent reasoning loops and race to write to `QueryCache` and `ReasoningTrace`.

**Fix:**
- Maintain an in-memory set of active `query_id`s
- A second stream request for an already-active `query_id` should wait for the result or return an error

---

### T3-5 Documents with zero headings are invisible to structural navigation

**Files:** `app/ingestion/structure.py:124`
**Severity:** MEDIUM

A document with no Markdown headings produces `toc_json = []`. The LLM cannot call `read_section` because there are no `node_id`s. All content is only reachable via `grep_documents`.

**Fix:**
- Create a synthetic root section (`s000` / "Full Document") when no headings are detected, so content remains navigable via structural tools

---

### T3-6 `doc_id` truncated to 12 characters — silent collision risk

**Files:** `app/api/routes/documents.py:43`
**Severity:** MEDIUM

Filenames sharing the same first 12 slug characters (e.g., `annual-report-2024.pdf` and `annual-report-2025.pdf` both become `annual-repo`) collide silently. The second upload overwrites the first with no warning.

**Fix:**
- Use a longer slug (e.g., 64 chars) or append a short hash suffix
- Warn explicitly when a doc_id collision is detected at upload time

---

### T3-7 `CITATION_PATTERN` doesn't cover Swiss-German/Italian document formats

**Files:** `app/core/evidence.py:28`
**Severity:** MEDIUM

The citation regex covers `Section|Abschnitt|Kapitel|Chapter` but not `§`, `Art.`, `Artikel`, `Punkt`, `Absatz`, `Articolo` — all common in Swiss policy and legal documents. Citations using these labels silently fail extraction and are reported as unverified.

**Fix:**
- Extend the pattern: add `§`, `Art\.?`, `Artikel`, `Punkt`, `Abs\.?`, `Articolo`, `Alinéa`, `Chiffre`

---

### T3-8 `grep_documents` `max_results` has no upper bound

**Files:** `app/core/tools.py:350`
**Severity:** MEDIUM

The LLM can pass `max_results=100000` and it is forwarded to `search_text(limit=max_results)` with no cap. Combined with large paragraphs, tool results can grow to megabytes and overflow the Claude context window.

**Fix:**
- Clamp `max_results` to a hard maximum (e.g., 20) in `_grep_documents`
- Add `maximum: 20` to the tool's JSON schema definition

---

### T3-9 `read_paragraphs` accepts unbounded `para_ids` list

**Files:** `app/core/tools.py:291`
**Severity:** HIGH

The `read_paragraphs` tool accepts an unbounded `list[str]`. The LLM could pass hundreds of IDs, generating a large `WHERE para_id IN (...)` query and returning an arbitrarily large payload.

**Fix:**
- Enforce a maximum of 50 items in `_read_paragraphs`
- Add `maxItems: 50` to the tool's JSON schema definition

---

## Tier 4 — Clean-up and Maintainability

| Item | Location | Action |
|---|---|---|
| `run()` and `run_with_progress()` duplicate the full reasoning loop | `orchestrator.py` | Extract `_execute_iteration()` shared method |
| `regenerate_with_strict_citations` is dead code | `evidence.py` | Wire it up in `_verify_and_finalize` or remove it |
| `_build_toc_json` references non-existent model attributes | `pipeline.py:1040` | Delete the dead method |
| `section_path` on `Section` and `Paragraph` never populated | `models.py`, `pipeline.py` | Populate in `_create_sections_recursive` or drop the columns |
| `QueryLog.query_id` missing database index | `models.py` | Add `Index("ix_query_log_query_id", "query_id")` |
| `UserFeedback.query_id` no foreign key or index | `models.py` | Add FK constraint or index |
| F-string logging with user-controlled data | `query.py:94,131,199` | Switch to `%`-style logging to prevent log injection |
| `_compute_latency_ms` uses DB write time as baseline | `query.py` | Capture `started_at` before orchestrator call for accurate timing |
| ReDoS risk in cross-reference regex patterns (`.+?`) | `cross_references.py` | Replace `.+?` with bounded `[^.\n]{1,100}` |
| `annotator.py` bare `except Exception` swallows unexpected errors | `annotator.py:186` | Change to `logger.exception(...)` at minimum |
| `_add_context` in `tools.py` is a silent no-op stub | `tools.py:367` | Implement context window logic or document the gap clearly |
| `AsyncAnthropic` import missing from `evidence.py` | `evidence.py:460` | Uses sync client in async context — fix with `AsyncAnthropic` |
| Cache timezone handling: `datetime.now(UTC).replace(tzinfo=None)` | `cache.py:295` | Use consistent timezone-aware datetimes throughout |
| `CacheManager.store_reasoning_trace` has no error handling | `cache.py:266` | Wrap in try/except; log failures without propagating |

---

## Implementation Priority Summary

```
Phase 1 — Before any real documents go in:
  ✦ T1-1  search_text: push filtering into SQL, add FTS5
  ✦ T1-2  SQLite WAL mode + connection timeout
  ✦ T1-3  Checkpoint / transaction desync + file hash verification
  ✦ T1-4  doc_id sanitization + String(12) → String(255)
  ✦ T1-5  toc_json per-document try/except in _load_toc_corpus

Phase 2 — Before production deployment:
  ✦ T2-1  Remove single-doc citation verification bypass
  ✦ T2-2  Prompt injection via doc metadata (use string.Template + XML escape)
  ✦ T2-3  Parallelize Haiku annotation with asyncio.gather + semaphore
  ✦ T2-5  L2 ToC corpus cache: move to module-level singleton
  ✦ T2-6  Replace sync Anthropic client with AsyncAnthropic
  ✦ T2-7  DB session lifecycle: close between SSE iterations
  ✦ T2-8  Client disconnect: finally block + CancelledError handling
  ✦ T2-9  read_section pagination (max 50 paragraphs + offset)
  ✦ T2-10 Rate limiting + global concurrency semaphore
  ✦ T2-11 Wire cache invalidation into document deletion path
  ✦ T2-12 DRY_RUN_CACHE_ONLY check at stream endpoint

Phase 3 — Robustness polish:
  ✦ T3-1  Tool call cycle detection + correction injection
  ✦ T3-2  Auto-record evidence after read_section/read_paragraphs
  ✦ T3-3  API failure mid-loop → partial synthesis fallback
  ✦ T3-4  Dual-stream guard (active query_id set)
  ✦ T3-5  Synthetic root section for headingless documents
  ✦ T3-7  CITATION_PATTERN expansion for Swiss doc formats
  ✦ T3-8  grep_documents max_results cap
  ✦ T3-9  read_paragraphs para_ids list size cap

Phase 4 — Clean-up:
  ✦ Dead code removal (_build_toc_json, regenerate_with_strict_citations)
  ✦ Index additions (QueryLog.query_id)
  ✦ DRY refactor of orchestrator loop (run / run_with_progress)
  ✦ Timezone consistency in cache layer
  ✦ Logging: % style, exception() for unexpected errors
```

---

*Generated by two-agent review on 2026-02-24. Source agents: code-reviewer (quality/performance/security) + devils-advocate (edge cases/failure modes). Synthesized by orchestrator.*