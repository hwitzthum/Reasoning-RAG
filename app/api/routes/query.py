"""Query API routes for question answering."""

import asyncio
import json
import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import FeedbackRequest, QueryRequest
from app.config import settings
from app.core.orchestrator import ReasoningOrchestrator
from app.storage.cache import CacheManager
from app.storage.database import get_db
from app.storage.models import QueryLog, UserFeedback

logger = logging.getLogger(__name__)


router = APIRouter()

# Query scope is not persisted on QueryLog yet. Keep a bounded in-memory map so
# scoped queries can be streamed/cached correctly even when clients hit /stream
# without passing doc_ids explicitly.
_pending_query_doc_scopes: dict[str, list[str] | None] = {}
_MAX_PENDING_QUERY_SCOPES = 1024
_QUERY_RATE_LIMIT_WINDOW_SECONDS = 60
_query_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
_query_rate_limit_lock = asyncio.Lock()
_ORCHESTRATOR_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(max(settings.max_concurrent_queries, 1))
_active_stream_query_ids: set[str] = set()
_active_stream_query_ids_lock = asyncio.Lock()


def _remember_query_scope(query_id: str, doc_ids: list[str] | None) -> None:
    _pending_query_doc_scopes[query_id] = doc_ids
    if len(_pending_query_doc_scopes) > _MAX_PENDING_QUERY_SCOPES:
        oldest_query_id = next(iter(_pending_query_doc_scopes))
        _pending_query_doc_scopes.pop(oldest_query_id, None)


def _resolve_query_scope(
    query_id: str,
    request_doc_ids: list[str] | None,
) -> list[str] | None:
    if request_doc_ids is not None:
        return request_doc_ids
    return _pending_query_doc_scopes.get(query_id)


def _build_stream_url(query_id: str, doc_ids: list[str] | None) -> str:
    stream_path = f"/api/query/{query_id}/stream"
    if not doc_ids:
        return stream_path
    query_string = urlencode([("doc_ids", doc_id) for doc_id in doc_ids])
    return f"{stream_path}?{query_string}"


async def _enforce_submit_rate_limit(client_host: str | None) -> None:
    """Apply a simple in-memory per-client rate limit for query submissions."""
    limit = settings.query_rate_limit_requests_per_minute
    if limit <= 0:
        return

    host_key = client_host or "unknown"
    now_monotonic = asyncio.get_running_loop().time()

    async with _query_rate_limit_lock:
        bucket = _query_rate_limit_buckets[host_key]
        while bucket and now_monotonic - bucket[0] >= _QUERY_RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: maximum {limit} query submissions per minute."
                ),
            )
        bucket.append(now_monotonic)


def _get_projected_query_cost_usd() -> float:
    """Return configured projected worst-case query cost used for admission control."""
    return max(float(settings.projected_query_cost_usd), 0.0)


def _compute_latency_ms(
    *,
    answer_data: dict | None,
    started_at: datetime,
) -> int:
    """Compute latency in milliseconds from answer payload or wall-clock fallback."""
    if answer_data:
        elapsed_seconds = answer_data.get("elapsed_seconds")
        if isinstance(elapsed_seconds, (int, float)) and elapsed_seconds >= 0:
            return int(round(float(elapsed_seconds) * 1000))

    baseline = started_at if started_at.tzinfo is not None else started_at.replace(tzinfo=UTC)
    elapsed = (datetime.now(UTC) - baseline).total_seconds()
    return max(int(round(elapsed * 1000)), 0)


@router.post("/query", response_model=dict)
async def submit_query(
    payload: QueryRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit a question for processing and return stream metadata."""
    if not payload.question or not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    await _enforce_submit_rate_limit(http_request.client.host if http_request.client else None)

    projected_cost_usd = _get_projected_query_cost_usd()
    if projected_cost_usd > settings.max_projected_query_cost_usd:
        raise HTTPException(
            status_code=503,
            detail=(
                "Projected query cost exceeds allowed threshold "
                f"(${projected_cost_usd:.2f} > ${settings.max_projected_query_cost_usd:.2f})."
            ),
        )

    query_id = str(uuid4())
    doc_scope = payload.doc_ids
    _remember_query_scope(query_id, doc_scope)

    cache_manager = CacheManager(db)
    cached_result = await cache_manager.get_query_result(
        payload.question,
        doc_scope,
    )

    if cached_result:
        logger.info("Cache hit for query: %s", query_id)
        query_log = QueryLog(
            query_id=query_id,
            query_text=payload.question,
            status="completed",
            cache_hit=True,
            latency_ms=0,
            confidence=cached_result.get("confidence"),
            iterations=cached_result.get("iterations"),
        )
        db.add(query_log)
        await db.commit()
        return {
            "query_id": query_id,
            "status": "cached",
            "stream_url": _build_stream_url(query_id, doc_scope),
            "cached": True,
        }

    if settings.dry_run_cache_only:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cache-only dry-run mode is enabled and no cached result "
                "was found for this query."
            ),
        )

    query_log = QueryLog(
        query_id=query_id,
        query_text=payload.question,
        status="processing",
        cache_hit=False,
    )
    db.add(query_log)
    await db.commit()

    logger.info(
        "Query submitted: %s - %s... (projected_cost_usd=%.2f)",
        query_id,
        payload.question[:50],
        projected_cost_usd,
    )

    return {
        "query_id": query_id,
        "status": "processing",
        "stream_url": _build_stream_url(query_id, doc_scope),
    }


@router.get("/query/{query_id}/stream")
async def stream_query_response(
    query_id: str,
    doc_ids: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Stream reasoning progress and final answer via Server-Sent Events."""
    bind = db.bind
    if bind is None:
        raise HTTPException(status_code=500, detail="Database session is not bound to an engine")

    session_factory = async_sessionmaker(bind=bind, class_=AsyncSession, expire_on_commit=False)

    async def event_generator():
        from sqlalchemy import select

        started_at = datetime.now(UTC)
        orchestrator_started_at: datetime | None = None
        terminal_status: str | None = None
        terminal_latency_ms: int | None = None
        trace_persisted = False
        stream_owner = False

        async with session_factory() as session:
            result = await session.execute(select(QueryLog).where(QueryLog.query_id == query_id))
            query_log = result.scalar_one_or_none()

        if not query_log:
            _pending_query_doc_scopes.pop(query_id, None)
            yield {
                "event": "error",
                "data": json.dumps({"error": "Query not found", "query_id": query_id}),
            }
            return

        effective_doc_scope = _resolve_query_scope(query_id, doc_ids)
        trace_events: list[dict] = [
            {
                "type": "user",
                "query_id": query_id,
                "query_text": query_log.query_text,
                "doc_scope": effective_doc_scope,
            }
        ]
        query_text = query_log.query_text

        async with _active_stream_query_ids_lock:
            if query_id in _active_stream_query_ids:
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {
                            "error": "Another stream is already active for this query_id.",
                            "query_id": query_id,
                        }
                    ),
                }
                return
            _active_stream_query_ids.add(query_id)
            stream_owner = True

        async def persist_trace(answer: str | None, latency_ms: int) -> None:
            nonlocal trace_persisted
            if trace_persisted:
                return
            try:
                async with session_factory() as session:
                    await CacheManager(session).store_reasoning_trace(
                        query_id=query_id,
                        query_text=query_text,
                        trace=trace_events,
                        answer=answer,
                        latency_ms=latency_ms,
                    )
                trace_persisted = True
            except Exception:
                logger.exception("Failed storing reasoning trace for query %s", query_id)

        async def update_query_log(
            *,
            status: str,
            error_message: str | None,
            cache_hit: bool | None = None,
            confidence: str | None = None,
            iterations: int | None = None,
            latency_ms: int | None = None,
        ) -> None:
            async with session_factory() as session:
                result = await session.execute(select(QueryLog).where(QueryLog.query_id == query_id))
                row = result.scalar_one_or_none()
                if row is None:
                    return
                row.status = status
                row.error_message = error_message
                if cache_hit is not None:
                    row.cache_hit = cache_hit
                row.confidence = confidence
                row.iterations = iterations
                row.latency_ms = latency_ms
                await session.commit()

        async def get_cached_result() -> dict | None:
            async with session_factory() as session:
                return await CacheManager(session).get_query_result(
                    query_text,
                    effective_doc_scope,
                )

        async def cache_query_result(answer_data: dict) -> None:
            async with session_factory() as session:
                await CacheManager(session).cache_query_result(
                    query_text,
                    effective_doc_scope,
                    answer_data,
                )

        cached_result = await get_cached_result()

        if cached_result:
            logger.info("Returning cached result for query: %s", query_id)
            trace_events.append(
                {
                    "type": "answer",
                    "cached": True,
                    "confidence": cached_result.get("confidence"),
                    "iterations": cached_result.get("iterations"),
                }
            )

            terminal_status = "completed"
            terminal_latency_ms = 0
            await update_query_log(
                status="completed",
                error_message=None,
                cache_hit=True,
                confidence=cached_result.get("confidence"),
                iterations=cached_result.get("iterations"),
                latency_ms=terminal_latency_ms,
            )

            await persist_trace(cached_result.get("answer"), terminal_latency_ms)
            _pending_query_doc_scopes.pop(query_id, None)

            yield {
                "event": "answer",
                "data": json.dumps(
                    {
                        "query_id": query_id,
                        **cached_result,
                        "cached": True,
                    }
                ),
            }
            return

        if settings.dry_run_cache_only:
            error_msg = (
                "Cache-only dry-run mode is enabled and no cached result "
                "was found for this query."
            )
            trace_events.append({"type": "error", "error": error_msg, "query_id": query_id})
            terminal_status = "failed"
            terminal_latency_ms = _compute_latency_ms(
                answer_data=None,
                started_at=started_at,
            )
            await update_query_log(
                status="failed",
                error_message=error_msg,
                latency_ms=terminal_latency_ms,
            )
            await persist_trace(None, terminal_latency_ms)
            _pending_query_doc_scopes.pop(query_id, None)
            yield {
                "event": "error",
                "data": json.dumps({"error": error_msg, "query_id": query_id}),
            }
            return

        try:
            async with _ORCHESTRATOR_CONCURRENCY_SEMAPHORE:
                orchestrator_started_at = datetime.now(UTC)
                async with session_factory() as reasoning_session:
                    orchestrator = ReasoningOrchestrator(reasoning_session)
                    async for event in orchestrator.run_with_progress(
                        query_id=query_id,
                        question=query_text,
                        doc_ids=effective_doc_scope,
                    ):
                        if event["type"] == "progress":
                            progress_data = event["data"]
                            trace_events.append({"type": "progress", **progress_data})
                            yield {
                                "event": "progress",
                                "data": json.dumps(progress_data),
                            }

                        elif event["type"] == "answer":
                            answer_data = event["data"]
                            trace_events.append(
                                {
                                    "type": "answer",
                                    "confidence": answer_data.get("confidence"),
                                    "iterations": answer_data.get("iterations"),
                                    "citation_count": len(answer_data.get("citations", [])),
                                    "elapsed_seconds": answer_data.get("elapsed_seconds"),
                                }
                            )

                            await cache_query_result(answer_data)

                            terminal_status = "completed"
                            terminal_latency_ms = _compute_latency_ms(
                                answer_data=answer_data,
                                started_at=orchestrator_started_at or started_at,
                            )
                            await update_query_log(
                                status="completed",
                                error_message=None,
                                confidence=answer_data.get("confidence"),
                                iterations=answer_data.get("iterations"),
                                latency_ms=terminal_latency_ms,
                            )

                            await persist_trace(answer_data.get("answer"), terminal_latency_ms)
                            logger.info("Query completed: %s", query_id)

                            _pending_query_doc_scopes.pop(query_id, None)
                            yield {
                                "event": "answer",
                                "data": json.dumps(
                                    {
                                        "query_id": query_id,
                                        **answer_data,
                                    }
                                ),
                            }
                            return

                        elif event["type"] == "error":
                            error_data = event["data"]
                            trace_events.append({"type": "error", **error_data})

                            terminal_status = "failed"
                            terminal_latency_ms = _compute_latency_ms(
                                answer_data=None,
                                started_at=orchestrator_started_at or started_at,
                            )
                            await update_query_log(
                                status="failed",
                                error_message=error_data.get("error"),
                                latency_ms=terminal_latency_ms,
                            )

                            await persist_trace(None, terminal_latency_ms)
                            logger.error("Query failed: %s - %s", query_id, error_data.get("error"))

                            _pending_query_doc_scopes.pop(query_id, None)
                            yield {
                                "event": "error",
                                "data": json.dumps(error_data),
                            }
                            return

        except asyncio.CancelledError:
            terminal_status = "cancelled"
            trace_events.append(
                {
                    "type": "error",
                    "error": "Client disconnected",
                    "query_id": query_id,
                }
            )
            raise
        except Exception as e:
            logger.exception("Unexpected error in query %s", query_id)

            trace_events.append({"type": "error", "error": str(e), "query_id": query_id})
            terminal_status = "failed"
            terminal_latency_ms = _compute_latency_ms(
                answer_data=None,
                started_at=orchestrator_started_at or started_at,
            )
            await update_query_log(
                status="failed",
                error_message=str(e),
                latency_ms=terminal_latency_ms,
            )

            await persist_trace(None, terminal_latency_ms)
            _pending_query_doc_scopes.pop(query_id, None)

            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "error": "Internal server error",
                        "query_id": query_id,
                    }
                ),
            }
        finally:
            _pending_query_doc_scopes.pop(query_id, None)
            if stream_owner:
                async with _active_stream_query_ids_lock:
                    _active_stream_query_ids.discard(query_id)
            if terminal_status == "cancelled":
                if terminal_latency_ms is None:
                    terminal_latency_ms = _compute_latency_ms(
                        answer_data=None,
                        started_at=orchestrator_started_at or started_at,
                    )
                await asyncio.shield(
                    update_query_log(
                        status="cancelled",
                        error_message="Client disconnected",
                        latency_ms=terminal_latency_ms,
                    )
                )
                await asyncio.shield(persist_trace(None, terminal_latency_ms))

    return EventSourceResponse(event_generator())


@router.post("/query/{query_id}/feedback", status_code=201)
async def submit_feedback(
    query_id: str,
    feedback: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit user feedback on a query result."""
    from sqlalchemy import select

    result = await db.execute(select(QueryLog).where(QueryLog.query_id == query_id))
    query_log = result.scalar_one_or_none()

    if not query_log:
        raise HTTPException(status_code=404, detail="Query not found")

    user_feedback = UserFeedback(
        query_id=query_id,
        rating=feedback.rating,
        category=feedback.category,
        details=feedback.details,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(user_feedback)
    await db.commit()

    logger.info(
        "Feedback received for query %s: rating=%s, category=%s",
        query_id,
        feedback.rating,
        feedback.category,
    )

    return {
        "message": "Feedback received",
        "query_id": query_id,
        "rating": feedback.rating,
    }
