# Core Reasoning Module

This module implements the core reasoning capabilities for the Reasoning-RAG system. It provides the tools, prompts, and verification logic needed for Claude Sonnet to perform iterative, structure-aware document QA.

## Module Contents

### `prompts.py`
**System prompt template for Claude Sonnet 4.5**

- `SYSTEM_PROMPT` - XML-tagged template with 9-step reasoning protocol
- Includes placeholders for dynamic ToC injection
- Defines citation format: `[Document Title, Section X.Y, p.N]`

Usage:
```python
from app.core.prompts import SYSTEM_PROMPT

# Inject ToC corpus at runtime
formatted_prompt = SYSTEM_PROMPT.format(toc_corpus=toc_json)
```

### `tools.py`
**7 tools for document navigation + execution handler**

**Tools List:**
1. `list_documents` - Discovery with topic/language filtering
2. `get_toc` - Navigate document structure
3. `read_section` - Read section content
4. `read_paragraphs` - Targeted paragraph reading
5. `grep_documents` - Text/regex search with cross-reference resolution
6. `search_fallback` - Embedding search (Phase 2)
7. `record_evidence` - Evidence tracking

**ToolHandler Class:**
```python
from app.core.tools import ToolHandler

handler = ToolHandler(db_session)
result = await handler.execute("read_section", {
    "doc_id": "doc123",
    "node_id": "s001.1"
})

# Access state
print(handler.evidence_log)        # Evidence collected
print(handler.visited_sections)    # Sections already read
```

### `evidence.py`
**Citation verification and confidence scoring**

**EvidenceVerifier:**
```python
from app.core.evidence import EvidenceVerifier

verifier = EvidenceVerifier()

# Extract citations from answer
citations = verifier.extract_citations(answer_text)

# Verify against evidence log
verified, unverified = verifier.verify(citations, evidence_log)

# Fuzzy quote matching (85% threshold)
is_match = verifier.match_quotes(quote, evidence_texts)
```

**Confidence Calculation:**
```python
from app.core.evidence import calculate_confidence

confidence = calculate_confidence(evidence_log, citations)
# Returns: {"level": "high|medium|low", "statement": "..."}
```

Citation verification does not auto-regenerate answers; unverified citations are flagged and omitted from verified output.

### `orchestrator.py`
**Timeout wrapper for query execution**

```python
from app.core.orchestrator import with_timeout, QueryTimeoutError

try:
    result = await with_timeout(
        long_running_query(),
        timeout_seconds=60
    )
except QueryTimeoutError as e:
    print(f"Query timed out after {e.elapsed_seconds}s")
```

## Design Principles

### 1. Structure-First Navigation
Tools prioritize ToC-based navigation over text search. The orchestrator should:
1. Review ToC
2. Select promising sections
3. Read content
4. Follow cross-references via `grep_documents`
5. Build evidence log

### 2. Citation Provenance
Three-layer safeguard against hallucinations:
- LLM can only cite retrieved para_ids
- Post-generation verification
- Fuzzy quote matching

### 3. Iterative Reasoning
Max 8 iterations per query:
- Each iteration: tool calls + evidence evaluation
- Visited sections tracked to avoid re-reading
- Evidence accumulates across iterations

### 4. Multilingual Support
All components handle DE, FR, IT, EN:
- System prompt instructs response in query language
- Tools work across all languages
- Cross-reference patterns support multilingual text

## Data Formats

### Paragraph ID
Format: `{doc_id}:{section_id}:p{index}`

Example: `doc_policy_ict_2025:s001.1:p002`

### Citation Format
Format: `[Document Title, Section X.Y, p.N]`

Example: `[ICT Security Policy, Section 4.2, p.5]`

### Evidence Log Item
```python
{
    "para_id": "doc123:s001:p001",
    "relevance": "Defines password rotation policy",
    "iteration": 2
}
```

## Integration Points

### Requires (from Storage):
- `DocumentRepository` (L1-S-006)
- `ParagraphRepository` (L1-S-007)
- `AsyncSession` (L1-S-005)

### Used By (in Level 2):
- `ReasoningOrchestrator` (L2-O-001, L2-O-002, L2-O-003)
- Query API routes (L2-F-002)

## Testing

Run Core module tests:
```bash
pytest tests/unit/test_tools.py
pytest tests/unit/test_evidence.py
pytest tests/unit/test_orchestrator.py
```

Verification script:
```bash
python scripts/verify_core_tasks.py
```

## Configuration

Relevant settings from `app/config.py`:
- `max_reasoning_iterations` - Default: 8
- `query_timeout_seconds` - Default: 60
- `reasoning_model` - Default: claude-sonnet-4-6
- `annotation_model` - Default: claude-haiku-4-5-20251001

## Next Steps (Level 2)

1. **L2-O-001**: Implement full orchestrator using these tools
2. **L2-O-002**: Build reasoning loop with `SYSTEM_PROMPT`
3. **L2-O-003**: Add SSE progress streaming
4. **L2-O-004**: Implement `search_fallback` with embeddings (Phase 2)

## Status

**Phase 1 (MVP):** ✅ Complete
- All 7 tools defined
- Evidence verification implemented
- Timeout wrapper ready

**Phase 2 (Multi-Document):** ⏳ Pending
- `search_fallback` implementation
- Embedding generation during ingestion

**Phase 3 (Production):** ⏳ Pending
- Confidence calibration based on evaluation results
- Enhanced error reporting
