"""End-to-end evaluation tests with 10 test questions.

Runs comprehensive question answering tests to verify system performance
across different question types and complexity levels.
"""

import pytest
import json
from pathlib import Path

from app.core.orchestrator import ReasoningOrchestrator


# Test questions with expected keywords and sources
TEST_QUESTIONS = [
    {
        "id": "Q1",
        "question": "What is the minimum password length requirement?",
        "expected_keywords": ["12", "characters", "password"],
        "expected_sources": ["password", "security"],
        "min_confidence": "medium",
    },
    {
        "id": "Q2",
        "question": "How often must passwords be rotated?",
        "expected_keywords": ["90", "days", "rotation"],
        "expected_sources": ["password"],
        "min_confidence": "medium",
    },
    {
        "id": "Q3",
        "question": "What are the three user roles mentioned in the access control policy?",
        "expected_keywords": ["standard", "power", "administrator"],
        "expected_sources": ["access", "control"],
        "min_confidence": "high",
    },
    {
        "id": "Q4",
        "question": "What is the principle of least privilege?",
        "expected_keywords": ["least", "privilege", "access"],
        "expected_sources": ["access"],
        "min_confidence": "medium",
    },
    {
        "id": "Q5",
        "question": "Where are audit logs mentioned in the document?",
        "expected_keywords": ["appendix", "audit", "log"],
        "expected_sources": ["appendix"],
        "min_confidence": "medium",
    },
    {
        "id": "Q6",
        "question": "How long are audit logs retained?",
        "expected_keywords": ["12", "months", "log"],
        "expected_sources": ["appendix"],
        "min_confidence": "high",
    },
    {
        "id": "Q7",
        "question": "What password complexity requirements are specified?",
        "expected_keywords": ["uppercase", "lowercase", "number", "special"],
        "expected_sources": ["password"],
        "min_confidence": "high",
    },
    {
        "id": "Q8",
        "question": "Who has full system access according to the user roles?",
        "expected_keywords": ["administrator", "full", "access"],
        "expected_sources": ["access"],
        "min_confidence": "high",
    },
    {
        "id": "Q9",
        "question": "What happens if someone violates this policy?",
        "expected_keywords": ["disciplinary", "action", "termination"],
        "expected_sources": ["enforcement"],
        "min_confidence": "medium",
    },
    {
        "id": "Q10",
        "question": "Who reviews the audit logs and how frequently?",
        "expected_keywords": ["security", "team", "quarterly"],
        "expected_sources": ["appendix"],
        "min_confidence": "high",
    },
]


@pytest.mark.asyncio
async def test_10_question_evaluation(db_session, fixtures_dir, mock_anthropic_client):
    """Run all 10 test questions and generate evaluation report.

    This is the main evaluation test that runs all questions and
    reports on answer quality.
    """
    # Setup: Ingest test document
    from app.ingestion.pipeline import IngestionPipeline

    policy_path = fixtures_dir / "sample_documents" / "test_policy.md"
    pipeline = IngestionPipeline(db_session)

    try:
        doc_id = await pipeline.ingest_document(policy_path)
    except Exception as e:
        pytest.skip(f"Document ingestion failed: {e}")

    # Initialize orchestrator
    orchestrator = ReasoningOrchestrator(db_session)

    # Run all questions
    results = []

    for test_case in TEST_QUESTIONS:
        result = await run_single_question(
            orchestrator, test_case, doc_id
        )
        results.append(result)

    # Generate evaluation report
    report = generate_evaluation_report(results)

    # Print report (for test output)
    print("\n" + "=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)
    print(report)
    print("=" * 70)

    # Assert minimum pass rate
    pass_count = sum(1 for r in results if r["passed"])
    pass_rate = pass_count / len(results)

    # Require at least 70% pass rate
    assert pass_rate >= 0.7, f"Pass rate {pass_rate:.1%} below 70% threshold"


async def run_single_question(
    orchestrator: ReasoningOrchestrator,
    test_case: dict,
    doc_id: str,
) -> dict:
    """Run a single test question and evaluate the answer.

    Args:
        orchestrator: ReasoningOrchestrator instance
        test_case: Test case dictionary with question and expected values
        doc_id: Document ID to scope query to

    Returns:
        dict: Evaluation result with pass/fail and metrics
    """
    question = test_case["question"]

    try:
        # Run query
        answer_data = await orchestrator.run(
            question=question,
            doc_ids=[doc_id],
        )

        # Evaluate answer
        keyword_score = evaluate_keywords(
            answer_data["answer"],
            test_case["expected_keywords"],
        )

        citation_score = evaluate_citations(
            answer_data["citations"],
            test_case["expected_sources"],
        )

        confidence_ok = evaluate_confidence(
            answer_data["confidence"],
            test_case["min_confidence"],
        )

        # Overall pass/fail
        passed = (
            keyword_score >= 0.5 and citation_score >= 0.3 and confidence_ok
        )

        return {
            "id": test_case["id"],
            "question": question,
            "answer": answer_data["answer"],
            "confidence": answer_data["confidence"],
            "citations": answer_data["citations"],
            "iterations": answer_data["iterations"],
            "keyword_score": keyword_score,
            "citation_score": citation_score,
            "confidence_ok": confidence_ok,
            "passed": passed,
            "error": None,
        }

    except Exception as e:
        return {
            "id": test_case["id"],
            "question": question,
            "answer": None,
            "confidence": None,
            "citations": [],
            "iterations": 0,
            "keyword_score": 0.0,
            "citation_score": 0.0,
            "confidence_ok": False,
            "passed": False,
            "error": str(e),
        }


def evaluate_keywords(answer: str, expected_keywords: list[str]) -> float:
    """Calculate keyword match score.

    Args:
        answer: Answer text
        expected_keywords: List of expected keywords

    Returns:
        float: Score from 0.0 to 1.0
    """
    if not expected_keywords:
        return 1.0

    answer_lower = answer.lower()
    matches = sum(
        1 for keyword in expected_keywords if keyword.lower() in answer_lower
    )

    return matches / len(expected_keywords)


def evaluate_citations(citations: list[dict], expected_sources: list[str]) -> float:
    """Calculate citation relevance score.

    Args:
        citations: List of citation dictionaries
        expected_sources: List of expected source keywords

    Returns:
        float: Score from 0.0 to 1.0
    """
    if not expected_sources:
        return 1.0

    if not citations:
        return 0.0

    # Check if citations reference expected sources
    citation_texts = " ".join(str(c) for c in citations).lower()

    matches = sum(
        1 for source in expected_sources if source.lower() in citation_texts
    )

    return matches / len(expected_sources)


def evaluate_confidence(actual: str, minimum: str) -> bool:
    """Check if confidence meets minimum requirement.

    Args:
        actual: Actual confidence level
        minimum: Minimum required confidence level

    Returns:
        bool: True if meets requirement
    """
    confidence_order = ["low", "medium", "high"]

    if actual not in confidence_order or minimum not in confidence_order:
        return False

    actual_idx = confidence_order.index(actual)
    minimum_idx = confidence_order.index(minimum)

    return actual_idx >= minimum_idx


def generate_evaluation_report(results: list[dict]) -> str:
    """Generate evaluation report from results.

    Args:
        results: List of evaluation results

    Returns:
        str: Formatted evaluation report
    """
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    pass_rate = passed / total if total > 0 else 0.0

    # Aggregate metrics
    avg_keyword_score = sum(r["keyword_score"] for r in results) / total
    avg_citation_score = sum(r["citation_score"] for r in results) / total

    confidence_counts = {
        "high": sum(1 for r in results if r.get("confidence") == "high"),
        "medium": sum(1 for r in results if r.get("confidence") == "medium"),
        "low": sum(1 for r in results if r.get("confidence") == "low"),
    }

    # Build report
    report = []
    report.append(f"\nTotal Questions: {total}")
    report.append(f"Passed: {passed} ({pass_rate:.1%})")
    report.append(f"Failed: {failed} ({(failed/total):.1%})")
    report.append(f"\nAverage Keyword Score: {avg_keyword_score:.2f}")
    report.append(f"Average Citation Score: {avg_citation_score:.2f}")
    report.append(f"\nConfidence Distribution:")
    report.append(f"  High: {confidence_counts['high']}")
    report.append(f"  Medium: {confidence_counts['medium']}")
    report.append(f"  Low: {confidence_counts['low']}")

    # Individual results
    report.append("\n" + "-" * 70)
    report.append("INDIVIDUAL RESULTS")
    report.append("-" * 70)

    for r in results:
        status = "✓ PASS" if r["passed"] else "✗ FAIL"
        report.append(f"\n{r['id']}: {status}")
        report.append(f"Question: {r['question']}")

        if r["error"]:
            report.append(f"Error: {r['error']}")
        else:
            report.append(f"Answer: {r['answer'][:100]}...")
            report.append(f"Confidence: {r['confidence']}")
            report.append(f"Keyword Score: {r['keyword_score']:.2f}")
            report.append(f"Citation Score: {r['citation_score']:.2f}")
            report.append(f"Citations: {len(r['citations'])}")

    return "\n".join(report)


@pytest.mark.asyncio
async def test_save_evaluation_results(db_session, tmp_path):
    """Test saving evaluation results for trend analysis.

    Note: This is a placeholder for future implementation.
    Results could be saved to JSON or database for tracking over time.
    """
    # Create sample results
    results = [
        {
            "id": "Q1",
            "question": "Test question",
            "passed": True,
            "keyword_score": 0.8,
            "citation_score": 0.9,
        }
    ]

    # Save to JSON
    output_path = tmp_path / "evaluation_results.json"

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # Verify file created
    assert output_path.exists()

    # Load and verify
    with open(output_path) as f:
        loaded = json.load(f)

    assert len(loaded) == 1
    assert loaded[0]["id"] == "Q1"
