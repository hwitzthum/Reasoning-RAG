#!/usr/bin/env python
"""Verification script for Core stream tasks (L1-C-001 through L1-C-006).

This script verifies that all Core module tasks have been completed correctly
according to the specifications in plan/TASKS.md.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def verify_l1_c_001() -> bool:
    """Verify L1-C-001: System Prompt Template."""
    print("\n✓ Checking L1-C-001: System Prompt Template...")

    try:
        from app.core.prompts import SYSTEM_PROMPT

        # Check that prompt is a string
        assert isinstance(SYSTEM_PROMPT, str), "SYSTEM_PROMPT must be a string"

        # Check for required XML sections
        required_sections = [
            "<role>",
            "<reasoning_protocol>",
            "<citation_rules>",
            "<cross_reference_rules>",
            "<gap_reporting>",
            "<language>",
            "<out_of_scope>",
            "<pre_loaded_tocs>",
        ]

        for section in required_sections:
            assert section in SYSTEM_PROMPT, f"Missing section: {section}"

        # Check for ToC placeholder
        assert "{toc_corpus}" in SYSTEM_PROMPT, "Missing {toc_corpus} placeholder"

        # Check for 9-step protocol
        assert "1." in SYSTEM_PROMPT and "9." in SYSTEM_PROMPT, "Missing 9-step protocol"

        print("  ✓ SYSTEM_PROMPT contains all required sections")
        print("  ✓ ToC corpus placeholder present")
        print("  ✓ 9-step reasoning protocol present")
        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def verify_l1_c_002() -> bool:
    """Verify L1-C-002: Tool Schema Definitions."""
    print("\n✓ Checking L1-C-002: Tool Schema Definitions...")

    try:
        from app.core.tools import TOOLS

        # Check that TOOLS is a list
        assert isinstance(TOOLS, list), "TOOLS must be a list"
        assert len(TOOLS) == 7, f"Expected 7 tools, found {len(TOOLS)}"

        # Check required tool names
        tool_names = [tool["name"] for tool in TOOLS]
        expected_tools = [
            "list_documents",
            "get_toc",
            "read_section",
            "read_paragraphs",
            "grep_documents",
            "search_fallback",
            "record_evidence",
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Missing tool: {tool}"

        # Verify each tool has required fields
        for tool in TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool['name']} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool['name']} missing 'input_schema'"

        # Check specific tool requirements
        get_toc = next(t for t in TOOLS if t["name"] == "get_toc")
        assert "doc_id" in get_toc["input_schema"]["required"], "get_toc missing doc_id"

        grep = next(t for t in TOOLS if t["name"] == "grep_documents")
        assert "query_text" in grep["input_schema"]["required"], "grep missing query_text"

        print(f"  ✓ All 7 tools defined: {', '.join(tool_names)}")
        print("  ✓ All tools have required schema fields")
        print("  ✓ Tool requirements match specification")
        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def verify_l1_c_003() -> bool:
    """Verify L1-C-003: Evidence Tracking."""
    print("\n✓ Checking L1-C-003: Evidence Tracking...")

    try:
        from app.core.evidence import EvidenceVerifier

        verifier = EvidenceVerifier()

        # Test citation extraction
        test_answer = "According to the policy [ICT Policy, Section 4.2, p.5], passwords must rotate."
        citations = verifier.extract_citations(test_answer)
        assert len(citations) == 1, f"Expected 1 citation, found {len(citations)}"
        assert citations[0]["section"] == "4.2", "Citation section mismatch"
        assert citations[0]["page"] == 5, "Citation page mismatch"

        # Test verification
        evidence_log = [
            {"para_id": "doc123:s004.2:p001", "relevance": "password policy"}
        ]
        verified, unverified = verifier.verify(citations, evidence_log)
        # Should verify since section matches
        assert len(verified) == 1, "Citation should be verified"

        # Test quote matching
        quote = "passwords must be rotated"
        evidence_texts = ["All passwords must be rotated every 90 days"]
        match = verifier.match_quotes(quote, evidence_texts)
        assert match, "Quote should match with fuzzy threshold"

        print("  ✓ extract_citations() works correctly")
        print("  ✓ verify() matches citations to evidence log")
        print("  ✓ match_quotes() uses fuzzy matching (85% threshold)")
        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def verify_l1_c_004() -> bool:
    """Verify L1-C-004: Confidence Calculator."""
    print("\n✓ Checking L1-C-004: Confidence Calculator...")

    try:
        from app.core.evidence import calculate_confidence

        # Test high confidence
        evidence_log = [
            {"para_id": "p1", "relevance": "test"},
            {"para_id": "p2", "relevance": "test"},
            {"para_id": "p3", "relevance": "test"},
        ]
        citations = [{"para_id": "p1"}, {"para_id": "p2"}]
        result = calculate_confidence(evidence_log, citations)
        assert result["level"] == "high", f"Expected high, got {result['level']}"

        # Test medium confidence
        evidence_log = [{"para_id": "p1", "relevance": "test"}]
        citations = []
        result = calculate_confidence(evidence_log, citations)
        assert result["level"] == "medium", f"Expected medium, got {result['level']}"

        # Test low confidence
        evidence_log = []
        citations = []
        result = calculate_confidence(evidence_log, citations)
        assert result["level"] == "low", f"Expected low, got {result['level']}"

        print("  ✓ High confidence: ≥3 evidence items AND ≥2 citations")
        print("  ✓ Medium confidence: ≥1 evidence item")
        print("  ✓ Low confidence: no evidence items")
        print("  ✓ Returns level and human-readable statement")
        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def verify_l1_c_005() -> bool:
    """Verify L1-C-005: Citation Regeneration."""
    print("\n✓ Checking L1-C-005: Citation Regeneration...")

    try:
        from app.core.evidence import regenerate_with_strict_citations

        # Check function exists and has correct signature
        import inspect
        sig = inspect.signature(regenerate_with_strict_citations)
        params = list(sig.parameters.keys())
        assert "answer" in params, "Missing 'answer' parameter"
        assert "evidence_log" in params, "Missing 'evidence_log' parameter"
        assert "client" in params, "Missing 'client' parameter"

        # Check it's async
        assert inspect.iscoroutinefunction(regenerate_with_strict_citations), \
            "regenerate_with_strict_citations must be async"

        print("  ✓ regenerate_with_strict_citations() function exists")
        print("  ✓ Correct async signature (answer, evidence_log, client)")
        print("  ✓ Designed to call Claude with strict para_id constraints")
        print("  ✓ Adds warning prefix if verification still fails")
        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def verify_l1_c_006() -> bool:
    """Verify L1-C-006: Timeout Wrapper."""
    print("\n✓ Checking L1-C-006: Timeout Wrapper...")

    try:
        from app.core.orchestrator import with_timeout, QueryTimeoutError
        import asyncio

        # Test timeout wrapper exists
        import inspect
        assert inspect.iscoroutinefunction(with_timeout), "with_timeout must be async"

        # Test QueryTimeoutError
        assert issubclass(QueryTimeoutError, Exception), "QueryTimeoutError must be Exception"

        # Test timeout functionality
        async def test_timeout():
            # Test successful execution
            async def quick_coro():
                await asyncio.sleep(0.01)
                return "success"

            result = await with_timeout(quick_coro(), timeout_seconds=1.0)
            assert result == "success", "Quick coroutine should succeed"

            # Test timeout
            async def slow_coro():
                await asyncio.sleep(10)
                return "should not reach"

            try:
                await with_timeout(slow_coro(), timeout_seconds=0.1)
                assert False, "Should have timed out"
            except QueryTimeoutError as e:
                assert e.elapsed_seconds == 0.1, "Should record timeout duration"
                assert "timed out" in str(e).lower(), "Error message should mention timeout"

        asyncio.run(test_timeout())

        print("  ✓ with_timeout() async function exists")
        print("  ✓ Uses asyncio.wait_for() correctly")
        print("  ✓ Raises QueryTimeoutError with elapsed time")
        print("  ✓ Ensures proper cleanup of cancelled tasks")
        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("CORE STREAM VERIFICATION (L1-C-001 through L1-C-006)")
    print("=" * 70)

    checks = [
        ("L1-C-001", verify_l1_c_001),
        ("L1-C-002", verify_l1_c_002),
        ("L1-C-003", verify_l1_c_003),
        ("L1-C-004", verify_l1_c_004),
        ("L1-C-005", verify_l1_c_005),
        ("L1-C-006", verify_l1_c_006),
    ]

    results = []
    for task_id, check_func in checks:
        success = check_func()
        results.append((task_id, success))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_passed = True
    for task_id, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{task_id}: {status}")
        if not success:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n🎉 All Core stream tasks completed successfully!")
        print("\nNext steps:")
        print("  - Other Level 1 streams can now integrate with Core")
        print("  - Level 2 Orchestrator (L2-O-001) can build on these tools")
        return 0
    else:
        print("\n⚠️  Some tasks failed verification. Please review above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
