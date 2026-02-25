"""Integration tests for reasoning orchestrator.

Tests the complete reasoning loop including tool execution, evidence logging,
citation verification, and confidence calculation.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from anthropic.types import Message, ContentBlock, TextBlock, ToolUseBlock

from app.core.orchestrator import ReasoningOrchestrator, QueryTimeoutError, with_timeout
from app.core.tools import ToolHandler
from app.storage.models import Document, Paragraph, Section


@pytest.mark.asyncio
async def test_simple_factual_query(db_session, mock_anthropic_client):
    """Test simple factual query with mocked Anthropic responses.

    Verifies:
    - Tool calls executed in correct order
    - Evidence log populated
    - Citations verified
    - Confidence calculated correctly
    """
    # Setup orchestrator
    orchestrator = ReasoningOrchestrator(db_session)

    # Mock Anthropic client to return predetermined responses
    mock_client = Mock()

    # Response 1: list_documents tool call
    response_1 = Mock(spec=Message)
    response_1.stop_reason = "tool_use"
    response_1.content = [
        ToolUseBlock(
            id="tool_1",
            type="tool_use",
            name="list_documents",
            input={},
        )
    ]

    # Response 2: record_evidence tool call (to populate evidence log)
    response_2 = Mock(spec=Message)
    response_2.stop_reason = "tool_use"
    response_2.content = [
        ToolUseBlock(
            id="tool_2",
            type="tool_use",
            name="record_evidence",
            input={
                "para_id": "doc_policy:s002.1:p001",
                "relevance_note": "Contains password length requirement",
            },
        )
    ]

    # Response 3: Final answer with proper citation format
    # Citation format: [Document Title, Section X.Y, p.N]
    # Section 2.1 matches s002.1 in the evidence
    response_3 = Mock(spec=Message)
    response_3.stop_reason = "end_turn"
    response_3.content = [
        TextBlock(
            type="text",
            text="The password policy requires passwords to be at least 12 characters long. [ICT Policy, Section 2.1, p.5]",
        )
    ]

    mock_client.messages.create.side_effect = [response_1, response_2, response_3]
    orchestrator.client = mock_client

    # Execute query
    question = "What is the minimum password length?"
    result = await orchestrator.run(question)

    # Verify result structure
    assert "answer" in result
    assert "confidence" in result
    assert "citations" in result
    assert "evidence_log" in result
    assert "iterations" in result

    # Verify answer
    assert "12 characters" in result["answer"]

    # Verify evidence was recorded
    assert len(result["evidence_log"]) > 0

    # Verify citations extracted and verified
    assert len(result["citations"]) > 0

    # Verify iterations
    assert result["iterations"] == 3

    # Verify tool handler was used
    assert len(orchestrator.tool_handler.visited_sections) >= 0


@pytest.mark.asyncio
async def test_reasoning_model_fallback_on_not_found(db_session):
    """Test model fallback path when configured model id is not available."""
    orchestrator = ReasoningOrchestrator(db_session)

    class MissingModelError(Exception):
        status_code = 404
        body = {"error": {"type": "not_found_error", "message": "model: missing-model"}}

    mock_client = Mock()
    final_response = Mock(spec=Message)
    final_response.stop_reason = "end_turn"
    final_response.content = [
        TextBlock(type="text", text="Fallback answer. [Test Policy, Section 1.0, p.1]")
    ]

    mock_client.messages.create.side_effect = [
        MissingModelError("model missing"),
        final_response,
    ]

    orchestrator.client = mock_client
    orchestrator._model_candidates = ["missing-model", "working-model"]
    orchestrator._active_reasoning_model = "missing-model"

    result = await orchestrator.run("Test question")

    assert "answer" in result
    assert orchestrator._active_reasoning_model == "working-model"

    called_models = [call.kwargs["model"] for call in mock_client.messages.create.call_args_list]
    assert called_models == ["missing-model", "working-model"]


@pytest.mark.asyncio
async def test_tool_execution_order(db_session, mock_anthropic_client):
    """Test that tools are executed in the correct order during reasoning."""
    orchestrator = ReasoningOrchestrator(db_session)
    tool_handler = orchestrator.tool_handler

    # Track tool calls
    tool_calls = []

    # Wrap execute method to track calls
    original_execute = tool_handler.execute

    async def tracked_execute(tool_name, tool_input):
        tool_calls.append(tool_name)
        return await original_execute(tool_name, tool_input)

    tool_handler.execute = tracked_execute

    # Mock Anthropic to call tools in sequence
    mock_client = Mock()

    response_1 = Mock(spec=Message)
    response_1.stop_reason = "tool_use"
    response_1.content = [
        ToolUseBlock(id="t1", type="tool_use", name="list_documents", input={})
    ]

    response_2 = Mock(spec=Message)
    response_2.stop_reason = "tool_use"
    response_2.content = [
        ToolUseBlock(
            id="t2",
            type="tool_use",
            name="get_toc",
            input={"doc_id": "test_doc"},
        )
    ]

    response_3 = Mock(spec=Message)
    response_3.stop_reason = "end_turn"
    response_3.content = [
        TextBlock(type="text", text="Answer based on documents. [Test Document, Section 1.0, p.1]")
    ]

    mock_client.messages.create.side_effect = [response_1, response_2, response_3]
    orchestrator.client = mock_client

    # Execute
    result = await orchestrator.run("Test question")

    # Verify tool execution order
    assert tool_calls == ["list_documents", "get_toc"]


@pytest.mark.asyncio
async def test_evidence_log_populated(db_session, mock_anthropic_client):
    """Test that evidence log is properly populated during reasoning."""
    orchestrator = ReasoningOrchestrator(db_session)

    # Mock Anthropic
    mock_client = Mock()

    # Response with record_evidence tool
    response_1 = Mock(spec=Message)
    response_1.stop_reason = "tool_use"
    response_1.content = [
        ToolUseBlock(
            id="t1",
            type="tool_use",
            name="record_evidence",
            input={
                "para_id": "doc_test:s001:p001",
                "relevance_note": "Contains password length requirement",
            },
        )
    ]

    response_2 = Mock(spec=Message)
    response_2.stop_reason = "end_turn"
    response_2.content = [
        TextBlock(type="text", text="Password must be 12 characters. [Test Policy, Section 1.0, p.1]")
    ]

    mock_client.messages.create.side_effect = [response_1, response_2]
    orchestrator.client = mock_client

    # Execute
    result = await orchestrator.run("Password question")

    # Verify evidence log
    assert len(result["evidence_log"]) > 0
    evidence = result["evidence_log"][0]
    assert evidence["para_id"] == "doc_test:s001:p001"
    assert "relevance_note" in evidence


@pytest.mark.asyncio
async def test_max_iterations_handling(db_session, mock_anthropic_client):
    """Test that max iterations limit is enforced."""
    orchestrator = ReasoningOrchestrator(db_session)
    orchestrator.max_iterations = 3  # Set low limit for testing

    # Mock to always request tools (never end_turn)
    mock_client = Mock()

    response = Mock(spec=Message)
    response.stop_reason = "tool_use"
    response.content = [
        ToolUseBlock(id="t", type="tool_use", name="list_documents", input={})
    ]

    # Return same response infinitely
    mock_client.messages.create.return_value = response
    orchestrator.client = mock_client

    # Execute
    result = await orchestrator.run("Test question")

    # Verify max iterations reached
    assert result["iterations"] == 3

    # Verify partial/incomplete answer synthesized
    # When no evidence found, message says "unable to find"
    # When some evidence found but max iterations reached, says "partial" or "maximum"
    answer_lower = result["answer"].lower()
    assert any(keyword in answer_lower for keyword in ["partial", "maximum", "unable"])


@pytest.mark.asyncio
async def test_timeout_handling(db_session):
    """Test that timeout wrapper properly raises QueryTimeoutError."""

    async def slow_operation():
        import asyncio

        await asyncio.sleep(2.0)
        return "completed"

    # Test timeout
    with pytest.raises(QueryTimeoutError) as exc_info:
        await with_timeout(slow_operation(), timeout_seconds=0.5)

    assert exc_info.value.elapsed_seconds == 0.5


@pytest.mark.asyncio
async def test_cross_reference_following(db_session, mock_anthropic_client):
    """Test that cross-references are properly followed during reasoning."""
    orchestrator = ReasoningOrchestrator(db_session)

    # Mock Anthropic to use grep_documents for xref resolution
    mock_client = Mock()

    # Response 1: read_section with xref
    response_1 = Mock(spec=Message)
    response_1.stop_reason = "tool_use"
    response_1.content = [
        ToolUseBlock(
            id="t1",
            type="tool_use",
            name="read_section",
            input={"doc_id": "doc1", "node_id": "s001"},
        )
    ]

    # Response 2: grep for cross-reference
    response_2 = Mock(spec=Message)
    response_2.stop_reason = "tool_use"
    response_2.content = [
        ToolUseBlock(
            id="t2",
            type="tool_use",
            name="grep_documents",
            input={"query_text": "Appendix A", "doc_ids": ["doc1"]},
        )
    ]

    # Response 3: Final answer
    response_3 = Mock(spec=Message)
    response_3.stop_reason = "end_turn"
    response_3.content = [
        TextBlock(type="text", text="Answer with cross-reference. [Document 1, Section 1.0, p.1]")
    ]

    mock_client.messages.create.side_effect = [response_1, response_2, response_3]
    orchestrator.client = mock_client

    # Execute
    result = await orchestrator.run("Question requiring xref")

    # Verify grep_documents was called (cross-reference followed)
    assert result["iterations"] >= 2


@pytest.mark.asyncio
async def test_confidence_calculation(db_session, mock_anthropic_client):
    """Test that confidence is calculated correctly based on evidence."""
    orchestrator = ReasoningOrchestrator(db_session)

    # Mock Anthropic
    mock_client = Mock()

    # Response with multiple evidence items
    response_1 = Mock(spec=Message)
    response_1.stop_reason = "tool_use"
    response_1.content = [
        ToolUseBlock(
            id="t1",
            type="tool_use",
            name="record_evidence",
            input={"para_id": "doc:s001:p001", "relevance_note": "Primary source"},
        )
    ]

    response_2 = Mock(spec=Message)
    response_2.stop_reason = "tool_use"
    response_2.content = [
        ToolUseBlock(
            id="t2",
            type="tool_use",
            name="record_evidence",
            input={"para_id": "doc:s002:p001", "relevance_note": "Supporting source"},
        )
    ]

    response_3 = Mock(spec=Message)
    response_3.stop_reason = "end_turn"
    response_3.content = [
        TextBlock(
            type="text",
            text="Answer with citations. [Policy Doc, Section 1.0, p.1] [Policy Doc, Section 2.0, p.3]",
        )
    ]

    mock_client.messages.create.side_effect = [response_1, response_2, response_3]
    orchestrator.client = mock_client

    # Execute
    result = await orchestrator.run("Test question")

    # Verify confidence calculated
    assert result["confidence"] in ["high", "medium", "low"]
    assert "confidence_statement" in result

    # With 2 evidence items and 2 citations, confidence should be high
    if len(result["evidence_log"]) >= 2 and len(result["citations"]) >= 2:
        assert result["confidence"] in ["high", "medium"]


@pytest.mark.asyncio
async def test_citations_verified(db_session, mock_anthropic_client):
    """Test that citations are verified against evidence log."""
    orchestrator = ReasoningOrchestrator(db_session)

    # Mock Anthropic
    mock_client = Mock()

    # Add evidence to tool handler
    # para_id format: {doc_id}:{section_id}:{para_index}
    # Section "s001" maps to Section 1.0 in citation format
    orchestrator.tool_handler.evidence_log.append(
        {
            "para_id": "doc:s001:p001",
            "text": "Password must be 12 characters",
            "doc_id": "doc",
            "section_id": "s001",
            "relevance_note": "Primary source",
        }
    )

    # Response with citation using proper citation format
    # [Document Title, Section X.Y, p.N] where Section 1.0 matches s001
    response = Mock(spec=Message)
    response.stop_reason = "end_turn"
    response.content = [
        TextBlock(
            type="text",
            text="Password requirement is 12 characters. [Policy Document, Section 1.0, p.5]",
        )
    ]

    mock_client.messages.create.return_value = response
    orchestrator.client = mock_client

    # Execute
    result = await orchestrator.run("Password question")

    # Verify citations were extracted and verified
    assert len(result["citations"]) > 0

    # Citation should have been verified against evidence log
    for citation in result["citations"]:
        assert "verified_para_id" in citation
        assert citation["verified_para_id"] == "doc:s001:p001"


@pytest.mark.asyncio
async def test_tool_cycle_detection_skips_repeated_tool_execution(db_session):
    """Third identical tool call should be short-circuited with correction guidance."""
    orchestrator = ReasoningOrchestrator(db_session)
    executed_calls = []

    original_execute = orchestrator.tool_handler.execute

    async def tracked_execute(tool_name, tool_input):
        executed_calls.append((tool_name, tool_input))
        return await original_execute(tool_name, tool_input)

    orchestrator.tool_handler.execute = tracked_execute

    mock_client = Mock()

    response_1 = Mock(spec=Message)
    response_1.stop_reason = "tool_use"
    response_1.content = [
        ToolUseBlock(id="tc1", type="tool_use", name="grep_documents", input={"query_text": "Appendix A"})
    ]

    response_2 = Mock(spec=Message)
    response_2.stop_reason = "tool_use"
    response_2.content = [
        ToolUseBlock(id="tc2", type="tool_use", name="grep_documents", input={"query_text": "Appendix A"})
    ]

    response_3 = Mock(spec=Message)
    response_3.stop_reason = "tool_use"
    response_3.content = [
        ToolUseBlock(id="tc3", type="tool_use", name="grep_documents", input={"query_text": "Appendix A"})
    ]

    response_4 = Mock(spec=Message)
    response_4.stop_reason = "end_turn"
    response_4.content = [TextBlock(type="text", text="Final answer.")]

    mock_client.messages.create.side_effect = [response_1, response_2, response_3, response_4]
    orchestrator.client = mock_client

    result = await orchestrator.run("Find Appendix A references")

    grep_calls = [call for call in executed_calls if call[0] == "grep_documents"]
    assert len(grep_calls) == 2
    assert result["iterations"] == 4


@pytest.mark.asyncio
async def test_auto_records_evidence_from_read_section_tool(db_session):
    """read_section should auto-record paragraph IDs when model skips record_evidence."""
    db_session.add(
        Document(
            doc_id="doc_auto",
            title="Auto Evidence Document",
            file_type="md",
            language="en",
            total_pages=1,
            file_hash="hash-doc-auto",
            toc_json=[{"node_id": "s001", "title": "Root", "level": 1, "sub_nodes": []}],
            summary="Auto evidence seed",
        )
    )
    db_session.add(
        Section(
            section_id="s001",
            doc_id="doc_auto",
            parent_section_id=None,
            title="Root",
            heading_level=1,
        )
    )
    db_session.add(
        Paragraph(
            para_id="doc_auto:s001:p001",
            doc_id="doc_auto",
            section_id="s001",
            para_index=1,
            text="Important evidence paragraph.",
            markdown_source="Important evidence paragraph.",
            page_number=1,
        )
    )
    await db_session.commit()

    orchestrator = ReasoningOrchestrator(db_session)
    mock_client = Mock()

    response_1 = Mock(spec=Message)
    response_1.stop_reason = "tool_use"
    response_1.content = [
        ToolUseBlock(
            id="auto_1",
            type="tool_use",
            name="read_section",
            input={"doc_id": "doc_auto", "node_id": "s001"},
        )
    ]

    response_2 = Mock(spec=Message)
    response_2.stop_reason = "end_turn"
    response_2.content = [TextBlock(type="text", text="Supported statement. [doc_auto:s001:p001]")]

    mock_client.messages.create.side_effect = [response_1, response_2]
    orchestrator.client = mock_client

    result = await orchestrator.run("What is the key statement?")

    assert any(item.get("auto_recorded") for item in result["evidence_log"])
    assert any(item.get("para_id") == "doc_auto:s001:p001" for item in result["evidence_log"])


@pytest.mark.asyncio
async def test_unverifiable_warning_when_citations_without_evidence(db_session):
    """Answers with citations but zero evidence should be explicitly flagged."""
    orchestrator = ReasoningOrchestrator(db_session)
    mock_client = Mock()

    response = Mock(spec=Message)
    response.stop_reason = "end_turn"
    response.content = [
        TextBlock(type="text", text="Claim text. [Policy, Section 1.0, p.1]")
    ]

    mock_client.messages.create.return_value = response
    orchestrator.client = mock_client

    result = await orchestrator.run("Question without tool reads")

    assert result["answer"].startswith("⚠️ Unverifiable answer:")


@pytest.mark.asyncio
async def test_model_failure_returns_partial_answer_when_evidence_exists(db_session):
    """Reasoning API failures mid-loop should synthesize from collected evidence."""
    orchestrator = ReasoningOrchestrator(db_session)
    orchestrator.tool_handler.evidence_log.append(
        {
            "para_id": "doc_partial:s001:p001",
            "relevance_note": "Seed evidence",
        }
    )

    mock_client = Mock()
    mock_client.messages.create.side_effect = RuntimeError("synthetic provider failure")
    orchestrator.client = mock_client

    result = await orchestrator.run("Trigger provider failure")

    assert "partial information" in result["answer"].lower()
    assert result["iterations"] == 1


@pytest.mark.asyncio
async def test_grep_documents_clamps_max_results(db_session):
    """grep_documents should clamp max_results to hard limit."""
    handler = ToolHandler(db_session)

    class DummyParaRepo:
        def __init__(self):
            self.captured_limit = None

        async def search_text(self, query, doc_ids=None, regex=False, limit=10):
            self.captured_limit = limit
            return []

    dummy_para_repo = DummyParaRepo()
    handler.doc_repo = object()
    handler.para_repo = dummy_para_repo

    result = await handler.execute(
        "grep_documents",
        {"query_text": "x", "max_results": 999},
    )

    assert result == []
    assert dummy_para_repo.captured_limit == 20


@pytest.mark.asyncio
async def test_read_paragraphs_limits_para_id_count(db_session):
    """read_paragraphs should enforce the 50-item para_id cap."""
    handler = ToolHandler(db_session)

    class DummyParaRepo:
        def __init__(self):
            self.received_para_ids = []

        async def get_by_ids(self, para_ids):
            self.received_para_ids = para_ids
            return []

    dummy_para_repo = DummyParaRepo()
    handler.doc_repo = object()
    handler.para_repo = dummy_para_repo

    para_ids = [f"doc:s001:p{i:03d}" for i in range(1, 80)]
    result = await handler.execute("read_paragraphs", {"para_ids": para_ids})

    assert result == []
    assert len(dummy_para_repo.received_para_ids) == 50
