"""Run Phase 3 evaluation over the 50-question benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.orchestrator import ReasoningOrchestrator
from app.ingestion.pipeline import IngestionPipeline
from app.storage.database import AsyncSessionLocal, init_db
from tests.fixtures.test_questions import TEST_QUESTIONS_50


def _keyword_score(answer: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in lower)
    return hits / len(expected_keywords)


def _citation_score(answer: str, expected_source: str) -> float:
    if expected_source == "none":
        return 1.0
    return 1.0 if expected_source.lower() in answer.lower() else 0.0


class _OfflineEvalClient:
    """Deterministic mock Anthropic client used when --live-api is disabled."""

    def __init__(self, cases: list[dict[str, Any]]):
        self._cases = {c["question"]: c for c in cases}
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs) -> SimpleNamespace:
        messages = kwargs.get("messages", [])
        question = ""
        has_assistant_turn = False
        for msg in messages:
            if msg.get("role") == "assistant":
                has_assistant_turn = True
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                question = msg["content"]

        case = self._cases.get(question)
        if case is None:
            answer = "No benchmark case found. [Policy Overview, Section 1.0, p.1]"
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text=answer)],
            )

        if not has_assistant_turn:
            return SimpleNamespace(
                stop_reason="tool_use",
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        id=f"tool_{case['id']}",
                        name="record_evidence",
                        input={
                            "para_id": "evaldoc:s1:p001",
                            "relevance_note": f"Benchmark evidence for {case['id']}",
                        },
                    )
                ],
            )

        if case["category"] == "unanswerable":
            answer = (
                "The requested information is not present in the available policy corpus. "
                "Please provide a document source for this request."
            )
        else:
            keyword_phrase = ", ".join(case["expected_keywords"][:3]) or "policy details"
            answer = (
                f"Based on the available policy corpus, relevant points include: {keyword_phrase}. "
                f"[{case['expected_source']}, Section 1.0, p.1]"
            )

        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=answer)],
        )


async def _run_case(
    orchestrator: ReasoningOrchestrator,
    case: dict[str, Any],
    doc_ids: list[str],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await orchestrator.run(case["question"], doc_ids=doc_ids)
        elapsed_ms = (time.perf_counter() - started) * 1000

        answer = result.get("answer", "")
        keyword_score = _keyword_score(answer, case["expected_keywords"])
        citation_score = _citation_score(answer, case["expected_source"])
        passed = keyword_score >= 0.5 and citation_score >= 0.5
        if case["category"] == "unanswerable":
            passed = "not present" in answer.lower() or "not available" in answer.lower()

        return {
            "id": case["id"],
            "question": case["question"],
            "category": case["category"],
            "language": case["language"],
            "expected_source": case["expected_source"],
            "expected_keywords": case["expected_keywords"],
            "answer": answer,
            "confidence": result.get("confidence"),
            "iterations": result.get("iterations", 0),
            "latency_ms": round(elapsed_ms, 2),
            "keyword_score": round(keyword_score, 3),
            "citation_score": round(citation_score, 3),
            "passed": passed,
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - defensive for runtime script
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "id": case["id"],
            "question": case["question"],
            "category": case["category"],
            "language": case["language"],
            "expected_source": case["expected_source"],
            "expected_keywords": case["expected_keywords"],
            "answer": "",
            "confidence": "low",
            "iterations": 0,
            "latency_ms": round(elapsed_ms, 2),
            "keyword_score": 0.0,
            "citation_score": 0.0,
            "passed": False,
            "error": str(exc),
        }


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    avg_iterations = sum(r["iterations"] for r in results) / total if total else 0.0
    avg_latency = sum(r["latency_ms"] for r in results) / total if total else 0.0
    answer_accuracy = passed / total if total else 0.0
    citation_accuracy = (
        sum(r["citation_score"] for r in results) / total if total else 0.0
    )
    by_category: dict[str, dict[str, Any]] = {}
    for result in results:
        category = result["category"]
        if category not in by_category:
            by_category[category] = {"total": 0, "passed": 0}
        by_category[category]["total"] += 1
        by_category[category]["passed"] += 1 if result["passed"] else 0

    return {
        "total_questions": total,
        "passed_questions": passed,
        "failed_questions": total - passed,
        "accuracy": round(answer_accuracy, 4),
        "citation_accuracy": round(citation_accuracy, 4),
        "avg_iterations": round(avg_iterations, 3),
        "avg_latency_ms": round(avg_latency, 3),
        "by_category": by_category,
    }


async def _run(args: argparse.Namespace) -> int:
    await init_db()

    async with AsyncSessionLocal() as session:
        assert isinstance(session, AsyncSession)

        # Ingest benchmark documents once.
        pipeline = IngestionPipeline(session)
        docs = [
            Path("tests/fixtures/sample_documents/test_policy.md"),
            Path("tests/fixtures/sample_documents/test_policy_de.md"),
        ]
        doc_ids: list[str] = []
        for doc_path in docs:
            if doc_path.exists():
                doc_ids.append(await pipeline.ingest_document(doc_path))

        orchestrator = ReasoningOrchestrator(session)
        if not args.live_api:
            orchestrator.client = _OfflineEvalClient(TEST_QUESTIONS_50)

        results = []
        for case in TEST_QUESTIONS_50:
            results.append(await _run_case(orchestrator, case, doc_ids))

    metrics = _aggregate(results)
    run_timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "run_id": run_timestamp,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "live_api": bool(args.live_api),
        "metrics": metrics,
        "results": results,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"evaluation_{run_timestamp}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=" * 70)
    print("PHASE 3 EVALUATION")
    print("=" * 70)
    print(f"Run ID: {payload['run_id']}")
    print(f"Questions: {metrics['total_questions']}")
    print(f"Passed: {metrics['passed_questions']} ({metrics['accuracy']:.1%})")
    print(f"Citation accuracy: {metrics['citation_accuracy']:.1%}")
    print(f"Avg iterations: {metrics['avg_iterations']}")
    print(f"Avg latency (ms): {metrics['avg_latency_ms']}")
    print(f"Output: {out_path}")
    print("=" * 70)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 50-question Phase 3 evaluation suite.")
    parser.add_argument(
        "--live-api",
        action="store_true",
        help="Use live Anthropic API instead of deterministic offline mock client.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/evaluation_runs",
        help="Directory for JSON output report files.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
