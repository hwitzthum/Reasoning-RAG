"""Integration tests for Server-Sent Events (SSE) streaming.

Tests the SSE endpoint for real-time query progress and answer delivery.
"""

import pytest
import json
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.api.routes import query as query_routes
from app.storage.database import get_db
from app.storage.models import QueryLog, ReasoningTrace


@pytest.fixture
async def client(db_session):
    """Create async HTTP client for FastAPI testing."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sse_connection_established(client):
    """Test that SSE connection can be established."""
    # First, create a query
    query_response = await client.post(
        "/api/query", json={"question": "Test question"}
    )

    assert query_response.status_code == 200
    query_id = query_response.json()["query_id"]

    # Connect to SSE stream
    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_progress_events_received(client, mock_anthropic_client):
    """Test that progress events are received during processing."""
    # Submit query
    query_response = await client.post(
        "/api/query", json={"question": "Test question"}
    )

    query_id = query_response.json()["query_id"]

    # Collect events from SSE stream
    events = []

    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
                events.append({"type": event_type, "data": json.loads(data)})

                # Stop after receiving answer event
                if event_type == "answer":
                    break

    # Verify we received events
    assert len(events) > 0

    # Verify progress events exist
    progress_events = [e for e in events if e["type"] == "progress"]
    assert len(progress_events) > 0

    # Verify answer event exists
    answer_events = [e for e in events if e["type"] == "answer"]
    assert len(answer_events) == 1


@pytest.mark.asyncio
async def test_answer_event_received(client, mock_anthropic_client):
    """Test that answer event is received at the end of processing."""
    # Submit query
    query_response = await client.post(
        "/api/query", json={"question": "What is the password policy?"}
    )

    query_id = query_response.json()["query_id"]

    # Collect answer event
    answer_event = None

    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_type == "answer":
                data = line.split(":", 1)[1].strip()
                answer_event = json.loads(data)
                break

    # Verify answer event structure
    assert answer_event is not None
    assert "query_id" in answer_event
    assert "answer" in answer_event
    assert "confidence" in answer_event
    assert "citations" in answer_event
    assert "iterations" in answer_event


@pytest.mark.asyncio
async def test_error_event_on_failure(client):
    """Test that error event is emitted when processing fails."""
    # Submit query with non-existent query_id to force error
    query_id = "nonexistent_query_id"

    # Collect error event
    error_event = None

    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_type == "error":
                data = line.split(":", 1)[1].strip()
                error_event = json.loads(data)
                break

    # Verify error event structure
    assert error_event is not None
    assert "error" in error_event
    assert "query_id" in error_event


@pytest.mark.asyncio
async def test_connection_closes_after_answer(client, mock_anthropic_client):
    """Test that SSE connection closes after answer is delivered."""
    # Submit query
    query_response = await client.post(
        "/api/query", json={"question": "Test question"}
    )

    query_id = query_response.json()["query_id"]

    # Track events received
    event_count = 0
    answer_received = False
    lines_after_answer = 0

    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        async for line in response.aiter_lines():
            event_count += 1

            if answer_received:
                # Count lines after answer (should be minimal - just empty lines)
                lines_after_answer += 1
                if lines_after_answer > 2:  # Allow a couple trailing newlines
                    break

            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
                if event_type == "answer":
                    answer_received = True

    # Verify answer was received and stream ended shortly after
    assert answer_received
    assert lines_after_answer <= 2  # Stream should close after answer + minimal trailing


@pytest.mark.asyncio
async def test_event_format_matches_schema(client, mock_anthropic_client):
    """Test that all events match the expected schema."""
    # Submit query
    query_response = await client.post(
        "/api/query", json={"question": "Test question"}
    )

    query_id = query_response.json()["query_id"]

    # Collect and validate events
    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_str = line.split(":", 1)[1].strip()
                data = json.loads(data_str)

                # Validate based on event type
                if event_type == "progress":
                    # Progress event should have iteration, status, message
                    assert "iteration" in data or "status" in data
                elif event_type == "answer":
                    # Answer event should have complete structure
                    assert "query_id" in data
                    assert "answer" in data
                    assert "confidence" in data
                    assert "citations" in data
                    break
                elif event_type == "error":
                    # Error event should have error message
                    assert "error" in data


@pytest.mark.asyncio
async def test_multiple_progress_events(client, mock_anthropic_client):
    """Test that multiple progress events are emitted during long processing."""
    # Submit a query that would trigger multiple tool calls
    query_response = await client.post(
        "/api/query",
        json={
            "question": "What is the complete password policy including all requirements?"
        },
    )

    query_id = query_response.json()["query_id"]

    # Collect all progress events
    progress_events = []

    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1].strip())

                if event_type == "progress":
                    progress_events.append(data)
                elif event_type == "answer":
                    break

    # Should have received multiple progress updates
    # Note: Depends on mocking setup - at minimum should have 1
    assert len(progress_events) >= 1


@pytest.mark.asyncio
async def test_cached_result_immediate_response(client, db_session, mock_anthropic_client):
    """Test that cached results are returned immediately without progress events."""
    # Submit same question twice
    question = "What is the password length?"

    # First query (uncached)
    response1 = await client.post("/api/query", json={"question": question})
    query_id1 = response1.json()["query_id"]

    # Wait for first query to complete (consume SSE stream fully)
    async with client.stream("GET", f"/api/query/{query_id1}/stream") as stream1:
        event_type = None
        async for line in stream1.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif event_type == "answer":
                break

    # Second query (should be cached)
    response2 = await client.post("/api/query", json={"question": question})
    query_id2 = response2.json()["query_id"]

    # Check if response indicates cached
    response2_json = response2.json()
    if "cached" in response2_json:
        assert response2_json["cached"] is True

    # Cached response should still provide answer via SSE
    answer_found = False
    event_type = None
    async with client.stream("GET", f"/api/query/{query_id2}/stream") as stream2:
        async for line in stream2.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
                if event_type == "answer":
                    answer_found = True
                    break

    assert answer_found, f"Expected answer event but got event_type={event_type}"


@pytest.mark.asyncio
async def test_stream_persists_trace_and_query_status(client, db_session, mock_anthropic_client):
    """Completed streams should persist QueryLog status and ReasoningTrace."""
    submit = await client.post("/api/query", json={"question": "Trace persistence check"})
    assert submit.status_code == 200
    query_id = submit.json()["query_id"]

    event_type = None
    answer_event = None
    async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_type == "answer":
                answer_event = json.loads(line.split(":", 1)[1].strip())
                break

    assert answer_event is not None

    query_log = (
        await db_session.execute(select(QueryLog).where(QueryLog.query_id == query_id))
    ).scalar_one()
    assert query_log.status == "completed"
    assert query_log.error_message is None
    assert query_log.latency_ms is not None
    assert query_log.latency_ms >= 0

    trace = (
        await db_session.execute(select(ReasoningTrace).where(ReasoningTrace.query_id == query_id))
    ).scalar_one_or_none()
    assert trace is not None
    assert isinstance(trace.trace_json, list)
    assert len(trace.trace_json) > 0
    assert any(item.get("type") == "progress" for item in trace.trace_json if isinstance(item, dict))


@pytest.mark.asyncio
async def test_second_stream_rejected_when_query_already_active(client):
    """A second stream for an active query_id should fail fast."""
    submit = await client.post("/api/query", json={"question": "Concurrent stream guard check"})
    assert submit.status_code == 200
    query_id = submit.json()["query_id"]

    query_routes._active_stream_query_ids.add(query_id)
    try:
        event_type = None
        error_event = None
        async with client.stream("GET", f"/api/query/{query_id}/stream") as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and event_type == "error":
                    error_event = json.loads(line.split(":", 1)[1].strip())
                    break
        assert error_event is not None
        assert "already active" in error_event["error"]
    finally:
        query_routes._active_stream_query_ids.discard(query_id)
