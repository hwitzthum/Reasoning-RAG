"""Admin API and admin page routes for Phase 3."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CacheStats, ConfigUpdate
from app.config import settings
from app.logging_config import configure_logging
from app.storage.cache import CacheManager
from app.storage.database import get_db
from app.storage.models import (
    Document,
    Embedding,
    IngestionCheckpoint,
    QueryCache,
    QueryLog,
    ReasoningTrace,
)
from app.storage.repositories import CrossReferenceRepository, DocumentRepository


api_router = APIRouter(prefix="/api/admin")
page_router = APIRouter(prefix="/admin")

# Backward-compatible alias for existing imports.
router = api_router

TEMPLATES = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[2] / "ui" / "templates")
)
EVAL_RUNS_DIR = Path("./data/evaluation_runs")
CONFIG_AUDIT_FILE = Path("./data/config_audit.log")


def _runtime_config_payload() -> dict[str, Any]:
    """Current runtime settings and restart requirements."""
    restart_required = {
        "max_reasoning_iterations": False,
        "query_timeout_seconds": False,
        "log_level": False,
        "dry_run_cache_only": False,
        "query_cache_ttl_seconds": False,
        "reasoning_model": True,
        "annotation_model": True,
    }
    return {
        "max_reasoning_iterations": settings.max_reasoning_iterations,
        "query_timeout_seconds": settings.query_timeout_seconds,
        "log_level": settings.log_level,
        "dry_run_cache_only": settings.dry_run_cache_only,
        "query_cache_ttl_seconds": settings.query_cache_ttl_seconds,
        "reasoning_model": settings.reasoning_model,
        "annotation_model": settings.annotation_model,
        "restart_required": restart_required,
    }


def _append_config_audit(changes: dict[str, Any]) -> None:
    """Append a JSON audit line for runtime config updates."""
    CONFIG_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "changes": changes,
    }
    with CONFIG_AUDIT_FILE.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(record) + "\n")


def _load_evaluation_runs(limit: int | None = None) -> list[dict[str, Any]]:
    """Load evaluation run JSON files from disk."""
    if not EVAL_RUNS_DIR.exists():
        return []

    files = sorted(EVAL_RUNS_DIR.glob("evaluation_*.json"), reverse=True)
    if limit is not None:
        files = files[:limit]

    runs: list[dict[str, Any]] = []
    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            payload["file_name"] = file_path.name
            payload["file_path"] = str(file_path)
            runs.append(payload)
        except Exception:
            continue
    return runs


def _parse_date_range(
    date_from: str | None,
    date_to: str | None,
) -> tuple[datetime | None, datetime | None]:
    """Parse YYYY-MM-DD filters into an inclusive start and exclusive end datetime."""
    start_dt: datetime | None = None
    end_dt: datetime | None = None

    if date_from:
        try:
            start_dt = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="date_from must use format YYYY-MM-DD",
            ) from exc

    if date_to:
        try:
            end_dt = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="date_to must use format YYYY-MM-DD",
            ) from exc

    if start_dt and end_dt and start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")

    return start_dt, end_dt


def _extract_sections_from_trace(trace_json: list[dict[str, Any]] | None) -> list[str]:
    """Extract section/node references from stored trace payloads."""
    if not trace_json:
        return []

    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            section_id = value.get("section_id")
            node_id = value.get("node_id")
            if isinstance(section_id, str) and section_id and section_id not in found:
                found.append(section_id)
            if isinstance(node_id, str) and node_id and node_id not in found:
                found.append(node_id)

            sections_explored = value.get("sections_explored")
            if isinstance(sections_explored, list):
                for item in sections_explored:
                    if isinstance(item, str) and item and item not in found:
                        found.append(item)

            for nested in value.values():
                walk(nested)
            return

        if isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(trace_json)
    return found


def _coerce_float_ms(value: Any) -> float:
    """Best-effort conversion for trace duration values."""
    if isinstance(value, (int, float)):
        return max(float(value), 0.0)
    if isinstance(value, str):
        try:
            return max(float(value), 0.0)
        except ValueError:
            return 0.0
    return 0.0


def _build_trace_view(
    trace_json: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build conversation and timeline payloads for trace rendering."""
    source_events = trace_json if isinstance(trace_json, list) else []

    events: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []

    for index, item in enumerate(source_events, start=1):
        event_type = str(item.get("type", "event")) if isinstance(item, dict) else "event"
        role = {
            "user": "user",
            "assistant": "assistant",
            "tool_call": "tool-call",
            "tool_result": "tool-result",
            "answer": "assistant",
            "progress": "event",
        }.get(event_type, "event")

        label = event_type
        if isinstance(item, dict):
            label = str(item.get("tool") or item.get("name") or event_type)

        payload = json.dumps(item, indent=2, ensure_ascii=True)
        iteration = item.get("iteration") if isinstance(item, dict) else None
        duration_ms = _coerce_float_ms(
            item.get("duration_ms") if isinstance(item, dict) else None
        ) or _coerce_float_ms(item.get("latency_ms") if isinstance(item, dict) else None)

        events.append(
            {
                "index": index,
                "type": event_type,
                "role": role,
                "label": label,
                "iteration": iteration,
                "payload": payload,
                "collapsible": event_type in {"tool_call", "tool_result"} or len(payload) > 300,
            }
        )
        timeline.append(
            {
                "index": index,
                "label": label,
                "iteration": iteration,
                "duration_ms": round(duration_ms, 2),
            }
        )

    if timeline:
        total_duration = sum(point["duration_ms"] for point in timeline)
        if total_duration > 0:
            for point in timeline:
                point["width_pct"] = round((point["duration_ms"] / total_duration) * 100.0, 2)
        else:
            width = round(100.0 / len(timeline), 2)
            for point in timeline:
                point["width_pct"] = width

    return events, timeline


def _highlight_citations(answer: str | None) -> Markup:
    """Render final answer with highlighted inline citations."""
    if not answer:
        return Markup("")

    escaped_answer = str(escape(answer))
    highlighted = re.sub(
        r"\[[^\]]+\]",
        lambda match: f'<mark class="citation-highlight">{match.group(0)}</mark>',
        escaped_answer,
    )
    return Markup(highlighted)


async def _compute_cache_stats(db: AsyncSession) -> CacheStats:
    """Compute cache and trace sizes + query cache hit rate."""
    docs_count = (await db.execute(select(func.count(Document.doc_id)))).scalar_one()
    embedding_count = (await db.execute(select(func.count(Embedding.para_id)))).scalar_one()
    l4_count = (await db.execute(select(func.count(QueryCache.query_hash)))).scalar_one()
    l5_count = (await db.execute(select(func.count(ReasoningTrace.query_id)))).scalar_one()
    query_count = (await db.execute(select(func.count(QueryLog.id)))).scalar_one()
    cache_hits = (
        await db.execute(select(func.count(QueryLog.id)).where(QueryLog.cache_hit.is_(True)))
    ).scalar_one()
    hit_rate = float(cache_hits) / float(query_count) if query_count else 0.0

    return CacheStats(
        l1_ingestion_size=int(docs_count),
        l2_toc_size=int(docs_count),
        l3_embeddings_size=int(embedding_count),
        l4_query_size=int(l4_count),
        l5_trace_size=int(l5_count),
        l4_hit_rate=hit_rate,
    )


async def _load_query_log_entries(
    db: AsyncSession,
    *,
    limit: int,
    confidence: str | None = None,
    cache_hit: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Load query log rows with optional filters and derived section exploration data."""
    stmt = select(QueryLog).order_by(QueryLog.created_at.desc()).limit(limit)

    if confidence in {"high", "medium", "low"}:
        stmt = stmt.where(QueryLog.confidence == confidence)
    if cache_hit in {"true", "false"}:
        stmt = stmt.where(QueryLog.cache_hit.is_(cache_hit == "true"))

    start_dt, end_dt = _parse_date_range(date_from, date_to)
    if start_dt:
        stmt = stmt.where(QueryLog.created_at >= start_dt)
    if end_dt:
        stmt = stmt.where(QueryLog.created_at < end_dt)

    rows = (await db.execute(stmt)).scalars().all()

    query_ids = [row.query_id for row in rows]
    sections_by_query: dict[str, list[str]] = {}
    if query_ids:
        trace_rows = (
            await db.execute(select(ReasoningTrace).where(ReasoningTrace.query_id.in_(query_ids)))
        ).scalars().all()
        sections_by_query = {
            row.query_id: _extract_sections_from_trace(row.trace_json)
            for row in trace_rows
        }

    return [
        {
            "query_id": row.query_id,
            "query_text": row.query_text,
            "cache_hit": row.cache_hit,
            "latency_ms": row.latency_ms,
            "iterations": row.iterations,
            "confidence": row.confidence,
            "sections_explored": sections_by_query.get(row.query_id, []),
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]


@api_router.get("/cache/stats", response_model=CacheStats)
async def get_cache_stats(
    db: AsyncSession = Depends(get_db),
) -> CacheStats:
    return await _compute_cache_stats(db)


@api_router.post("/cache/invalidate", status_code=204, response_class=Response)
async def invalidate_cache(
    doc_id: str | None = None,
    cache_layer: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Response:
    cache_manager = CacheManager(db)
    if doc_id:
        await cache_manager.invalidate_for_document(doc_id)
        return Response(status_code=204)

    if not cache_layer:
        raise HTTPException(status_code=400, detail="Provide either doc_id or cache_layer")

    layer = cache_layer.upper()
    if layer not in {"L1", "L2", "L3", "L4", "L5"}:
        raise HTTPException(status_code=400, detail="cache_layer must be one of L1..L5")

    if layer == "L2":
        cache_manager.invalidate_toc_corpus()
    elif layer == "L3":
        await db.execute(delete(Embedding))
        await db.commit()
    elif layer == "L4":
        await db.execute(delete(QueryCache))
        await db.commit()
    elif layer == "L5":
        await db.execute(delete(ReasoningTrace))
        await db.commit()
    # L1 is file/content-ingestion cache represented by documents and is not
    # globally dropped through this endpoint to avoid destructive operations.
    return Response(status_code=204)


@api_router.get("/queries/recent", response_model=list[dict])
async def get_recent_queries(
    limit: int = Query(default=50, ge=1, le=500),
    confidence: str | None = Query(default=None),
    cache_hit: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await _load_query_log_entries(
        db,
        limit=limit,
        confidence=confidence,
        cache_hit=cache_hit,
        date_from=date_from,
        date_to=date_to,
    )


@api_router.get("/traces/{query_id}", response_model=dict)
async def get_reasoning_trace(
    query_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    trace_result = await db.execute(
        select(ReasoningTrace).where(ReasoningTrace.query_id == query_id)
    )
    trace = trace_result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Reasoning trace for query {query_id} not found")

    return {
        "query_id": trace.query_id,
        "query_text": trace.query_text,
        "trace_json": trace.trace_json,
        "answer": trace.answer,
        "latency_ms": trace.latency_ms,
        "iterations": trace.iterations,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
    }


@api_router.get("/config", response_model=dict)
async def get_runtime_config(
    db: AsyncSession = Depends(get_db),
) -> dict:
    del db
    return _runtime_config_payload()


@api_router.put("/config", response_model=dict)
async def update_runtime_config(
    config: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    del db
    changes: dict[str, Any] = {}

    if config.max_reasoning_iterations is not None:
        settings.max_reasoning_iterations = config.max_reasoning_iterations
        changes["max_reasoning_iterations"] = config.max_reasoning_iterations
    if config.query_timeout_seconds is not None:
        settings.query_timeout_seconds = config.query_timeout_seconds
        changes["query_timeout_seconds"] = config.query_timeout_seconds
    if config.log_level is not None:
        settings.log_level = config.log_level
        configure_logging()
        changes["log_level"] = config.log_level
    if config.dry_run_cache_only is not None:
        settings.dry_run_cache_only = config.dry_run_cache_only
        changes["dry_run_cache_only"] = config.dry_run_cache_only
    if config.query_cache_ttl_seconds is not None:
        settings.query_cache_ttl_seconds = config.query_cache_ttl_seconds
        changes["query_cache_ttl_seconds"] = config.query_cache_ttl_seconds

    if changes:
        _append_config_audit(changes)

    payload = _runtime_config_payload()
    payload["updated"] = changes
    return payload


@page_router.get("/evaluation", response_class=HTMLResponse)
async def evaluation_dashboard(
    request: Request,
    run_a: str | None = None,
    run_b: str | None = None,
    question_id: str | None = None,
) -> HTMLResponse:
    runs = _load_evaluation_runs()
    lookup = {run["file_name"]: run for run in runs}
    selected_a = lookup.get(run_a) if run_a else (runs[0] if runs else None)
    selected_b = lookup.get(run_b) if run_b else (runs[1] if len(runs) > 1 else None)

    trend_points = [
        {
            "label": run.get("run_id", run["file_name"]),
            "timestamp": run.get("timestamp"),
            "accuracy": run.get("metrics", {}).get("accuracy", 0.0),
            "citation_accuracy": run.get("metrics", {}).get("citation_accuracy", 0.0),
        }
        for run in reversed(runs)
    ]

    selected_question: dict[str, Any] | None = None
    results = selected_a.get("results", []) if selected_a else []
    if results:
        selected_question = results[0]
        if question_id:
            selected_question = next((row for row in results if row.get("id") == question_id), results[0])

    return TEMPLATES.TemplateResponse(
        request=request,
        name="admin/evaluation.html",
        context={
            "runs": runs,
            "selected_a": selected_a,
            "selected_b": selected_b,
            "selected_question": selected_question,
            "question_id": question_id or "",
            "trend_points": trend_points,
        },
    )


@page_router.get("/documents", response_class=HTMLResponse)
async def documents_dashboard(
    request: Request,
    q: str | None = None,
    language: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    doc_repo = DocumentRepository(db)
    docs = await doc_repo.list_documents(topic=q, language=language)

    xref_repo = CrossReferenceRepository(db)
    unresolved = await xref_repo.get_unresolved()
    unresolved_by_doc: dict[str, int] = {}
    for item in unresolved:
        doc_id = item.source_para_id.split(":", maxsplit=1)[0]
        unresolved_by_doc[doc_id] = unresolved_by_doc.get(doc_id, 0) + 1

    ingestion_status_by_doc: dict[str, str] = {}
    doc_ids = [doc.doc_id for doc in docs]
    if doc_ids:
        checkpoint_rows = (
            await db.execute(
                select(IngestionCheckpoint).where(IngestionCheckpoint.doc_id.in_(doc_ids))
            )
        ).scalars().all()
        for checkpoint in checkpoint_rows:
            if checkpoint.error_message:
                ingestion_status_by_doc[checkpoint.doc_id] = "failed"
            else:
                ingestion_status_by_doc[checkpoint.doc_id] = f"in_progress ({checkpoint.stage})"
    for doc in docs:
        ingestion_status_by_doc.setdefault(doc.doc_id, "completed")

    return TEMPLATES.TemplateResponse(
        request=request,
        name="admin/documents.html",
        context={
            "documents": docs,
            "q": q or "",
            "language": language or "",
            "unresolved_by_doc": unresolved_by_doc,
            "ingestion_status_by_doc": ingestion_status_by_doc,
        },
    )


@page_router.get("/cache", response_class=HTMLResponse)
async def cache_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    stats = await _compute_cache_stats(db)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="admin/cache.html",
        context={
            "stats": stats,
            "runtime": _runtime_config_payload(),
        },
    )


@page_router.get("/queries", response_class=HTMLResponse)
async def queries_dashboard(
    request: Request,
    confidence: str | None = None,
    cache_hit: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    export: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    entries = await _load_query_log_entries(
        db,
        limit=500,
        confidence=confidence,
        cache_hit=cache_hit,
        date_from=date_from,
        date_to=date_to,
    )

    if export == "csv":
        stream = io.StringIO()
        fieldnames = [
            "query_id",
            "query_text",
            "cache_hit",
            "latency_ms",
            "iterations",
            "confidence",
            "sections_explored",
            "created_at",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            csv_entry = dict(entry)
            csv_entry["sections_explored"] = "; ".join(entry.get("sections_explored", []))
            writer.writerow(csv_entry)
        return PlainTextResponse(
            stream.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=queries.csv"},
        )

    return TEMPLATES.TemplateResponse(
        request=request,
        name="admin/queries.html",
        context={
            "entries": entries,
            "confidence": confidence or "",
            "cache_hit": cache_hit or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
        },
    )


@page_router.get("/trace/{query_id}", response_class=HTMLResponse)
async def trace_dashboard(
    query_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    trace_result = await db.execute(
        select(ReasoningTrace).where(ReasoningTrace.query_id == query_id)
    )
    trace = trace_result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace not found for {query_id}")

    trace_events, timeline = _build_trace_view(trace.trace_json)

    return TEMPLATES.TemplateResponse(
        request=request,
        name="admin/trace.html",
        context={
            "trace": trace,
            "trace_events": trace_events,
            "timeline": timeline,
            "highlighted_answer": _highlight_citations(trace.answer),
        },
    )


@page_router.get("/config", response_class=HTMLResponse)
async def config_dashboard(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request=request,
        name="admin/config.html",
        context={"config": _runtime_config_payload(), "message": ""},
    )


@page_router.post("/config", response_class=HTMLResponse)
async def config_update_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    form = await request.form()

    dry_run_values = [str(value).lower() for value in form.getlist("dry_run_cache_only")]
    dry_run_cache_only = None
    if dry_run_values:
        dry_run_cache_only = dry_run_values[-1] in {"1", "true", "on", "yes"}

    parsed = ConfigUpdate(
        max_reasoning_iterations=(
            int(form["max_reasoning_iterations"])
            if form.get("max_reasoning_iterations")
            else None
        ),
        query_timeout_seconds=(
            int(form["query_timeout_seconds"])
            if form.get("query_timeout_seconds")
            else None
        ),
        log_level=(str(form["log_level"]).upper() if form.get("log_level") else None),
        dry_run_cache_only=dry_run_cache_only,
        query_cache_ttl_seconds=(
            int(form["query_cache_ttl_seconds"])
            if form.get("query_cache_ttl_seconds")
            else None
        ),
    )
    payload = await update_runtime_config(parsed, db=db)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="admin/config.html",
        context={"config": payload, "message": "Configuration updated."},
    )
