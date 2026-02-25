"""Reasoning orchestrator and timeout utilities.

This module contains the reasoning loop orchestrator using Claude Sonnet
and the timeout wrapper for query execution.
"""

import asyncio
import hashlib
import json
from inspect import isawaitable
import logging
import re
import time
from string import Template
from typing import TypeVar, Coroutine, Any, AsyncIterator
from xml.sax.saxutils import escape as xml_escape
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.tools import ToolHandler, TOOLS
from app.core.prompts import SYSTEM_PROMPT
from app.core.evidence import EvidenceVerifier, calculate_confidence


T = TypeVar('T')

logger = logging.getLogger(__name__)

DEFAULT_REASONING_MODEL_FALLBACKS = [
    "claude-sonnet-4-6",
    "claude-sonnet-4-latest",
]


def _build_model_candidates(primary_model: str) -> list[str]:
    """Build a de-duplicated list of model candidates for graceful fallback."""
    primary = (primary_model or "").strip()
    candidates: list[str] = []

    if primary:
        candidates.append(primary)

        # Convert dated model IDs to provider aliases when possible.
        if re.search(r"-20\d{6}$", primary):
            base = primary.rsplit("-", 1)[0]
            candidates.extend([f"{base}-latest", base])
        elif primary.endswith("-latest"):
            base = primary[:-7]
            if base:
                candidates.append(base)
        else:
            candidates.append(f"{primary}-latest")

    candidates.extend(DEFAULT_REASONING_MODEL_FALLBACKS)

    deduped: list[str] = []
    for model in candidates:
        model_name = model.strip()
        if model_name and model_name not in deduped:
            deduped.append(model_name)

    return deduped


def _is_model_not_found_error(exc: Exception) -> bool:
    """Return True when the exception indicates an unknown model identifier."""
    status_code = getattr(exc, "status_code", None)
    if status_code != 404:
        return False

    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error_obj = body.get("error") if isinstance(body.get("error"), dict) else {}
        error_type = str(error_obj.get("type", "")).lower()
        error_message = str(error_obj.get("message", "")).lower()
        if error_type == "not_found_error" and "model" in error_message:
            return True

    message = str(exc).lower()
    return "model" in message and ("not_found" in message or "not found" in message)


class QueryTimeoutError(Exception):
    """Raised when a query exceeds the configured timeout."""

    def __init__(self, elapsed_seconds: float):
        self.elapsed_seconds = elapsed_seconds
        super().__init__(
            f"Query execution timed out after {elapsed_seconds:.1f} seconds"
        )


async def with_timeout(coro: Coroutine[Any, Any, T], timeout_seconds: float) -> T:
    """Execute a coroutine with timeout.

    This wrapper ensures queries don't run indefinitely. It provides
    clean cancellation and informative error messages.

    Args:
        coro: The coroutine to execute
        timeout_seconds: Maximum execution time in seconds

    Returns:
        The result of the coroutine

    Raises:
        QueryTimeoutError: If execution exceeds timeout_seconds

    Example:
        >>> result = await with_timeout(
        ...     orchestrator.run(question),
        ...     timeout_seconds=60
        ... )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise QueryTimeoutError(timeout_seconds)


class ReasoningOrchestrator:
    """Main reasoning loop orchestrator using Claude Sonnet.

    Executes iterative document navigation with tool use to answer questions
    about internal policy and regulatory documents.

    Attributes:
        db: Async database session
        client: Anthropic API client
        tool_handler: Handler for executing tool calls
        evidence_verifier: Citation verification
        max_iterations: Maximum reasoning iterations (default: 8)
    """

    def __init__(self, db: AsyncSession):
        """Initialize orchestrator with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.tool_handler = ToolHandler(db)
        self.evidence_verifier = EvidenceVerifier()
        self.max_iterations = settings.max_reasoning_iterations
        self._model_candidates = _build_model_candidates(settings.reasoning_model)
        self._active_reasoning_model = self._model_candidates[0]
        self._tool_call_counts: dict[tuple[str, str], int] = {}

    def _tool_input_hash(self, tool_name: str, tool_input: dict) -> str:
        """Return canonical hash for cycle-detection across repeated tool calls."""
        try:
            payload = json.dumps(tool_input, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        except TypeError:
            payload = repr(tool_input)
        return hashlib.sha256(f"{tool_name}|{payload}".encode("utf-8")).hexdigest()

    def _get_redundant_tool_message(self) -> str:
        return "You have already tried this. Explore a different section or synthesize from current evidence."

    async def run(
        self,
        question: str,
        doc_ids: list[str] | None = None,
    ) -> dict:
        """Run reasoning loop to answer a question.

        Executes iterative reasoning with Claude Sonnet, using tools to navigate
        documents and build evidence. Continues until answer found or max
        iterations reached.

        Args:
            question: User's question about documents
            doc_ids: Optional list of document IDs to scope search

        Returns:
            Dictionary with keys:
                - answer: The synthesized answer text
                - confidence: Confidence level (high/medium/low)
                - confidence_statement: Human-readable confidence explanation
                - citations: List of citation dictionaries
                - evidence_log: List of evidence items collected
                - sections_explored: List of section keys visited
                - iterations: Number of reasoning iterations used

        """
        # Load ToC corpus for system prompt
        toc_corpus = await self._load_toc_corpus(doc_ids)
        system_prompt = Template(SYSTEM_PROMPT).safe_substitute(toc_corpus=toc_corpus)

        messages = [{"role": "user", "content": question}]
        iteration = 0
        self._tool_call_counts.clear()

        while iteration < self.max_iterations:
            iteration += 1
            iteration_result = await self._execute_iteration(
                iteration=iteration,
                system_prompt=system_prompt,
                messages=messages,
                include_progress=False,
            )
            if iteration_result["completed"]:
                return iteration_result["result"]

        # Max iterations reached - synthesize partial answer
        return await self._synthesize_partial_answer(iteration)

    async def run_with_progress(
        self,
        query_id: str,
        question: str,
        doc_ids: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        """Run reasoning loop with SSE progress streaming.

        Yields progress events during reasoning and final answer event.
        This is the streaming version of run() for real-time UI updates.

        Args:
            query_id: Unique identifier for this query
            question: User's question about documents
            doc_ids: Optional list of document IDs to scope search

        Yields:
            Progress events: {"type": "progress", "data": {...}}
            Answer event: {"type": "answer", "data": {...}}
            Error event: {"type": "error", "data": {"error": "..."}}

        Example events:
            {"type": "progress", "data": {"iteration": 1, "tool": "get_toc", "status": "executing"}}
            {"type": "answer", "data": {"answer": "...", "confidence": "high", ...}}
        """
        start_time = time.time()

        try:
            # Load ToC corpus for system prompt
            yield {
                "type": "progress",
                "data": {
                    "iteration": 0,
                    "status": "loading_documents",
                    "message": "Loading document structure...",
                }
            }

            toc_corpus = await self._load_toc_corpus(doc_ids)
            system_prompt = Template(SYSTEM_PROMPT).safe_substitute(toc_corpus=toc_corpus)

            messages = [{"role": "user", "content": question}]
            iteration = 0
            self._tool_call_counts.clear()

            while iteration < self.max_iterations:
                iteration += 1

                # Emit iteration start
                yield {
                    "type": "progress",
                    "data": {
                        "iteration": iteration,
                        "status": "reasoning",
                        "message": f"Reasoning iteration {iteration}...",
                    }
                }

                iteration_result = await self._execute_iteration(
                    iteration=iteration,
                    system_prompt=system_prompt,
                    messages=messages,
                    include_progress=True,
                )

                for progress_event in iteration_result["progress_events"]:
                    yield {
                        "type": "progress",
                        "data": progress_event,
                    }

                if iteration_result["completed"]:
                    result = iteration_result["result"]
                    elapsed_time = time.time() - start_time
                    result["elapsed_seconds"] = round(elapsed_time, 2)
                    yield {
                        "type": "answer",
                        "data": result,
                    }
                    return

            # Max iterations reached - synthesize partial answer
            yield {
                "type": "progress",
                "data": {
                    "iteration": iteration,
                    "status": "synthesizing",
                    "message": "Maximum iterations reached, synthesizing partial answer...",
                }
            }

            result = await self._synthesize_partial_answer(iteration)
            elapsed_time = time.time() - start_time
            result["elapsed_seconds"] = round(elapsed_time, 2)

            yield {
                "type": "answer",
                "data": result,
            }

        except Exception as e:
            # Yield error event
            yield {
                "type": "error",
                "data": {
                    "error": str(e),
                    "query_id": query_id,
                }
            }

    async def _execute_iteration(
        self,
        *,
        iteration: int,
        system_prompt: str,
        messages: list[dict],
        include_progress: bool,
    ) -> dict[str, Any]:
        """Run one reasoning iteration shared by run() and run_with_progress()."""
        progress_events: list[dict] = []

        try:
            response = await self._create_reasoning_response(system_prompt, messages)
        except Exception:
            if self.tool_handler.evidence_log:
                logger.exception(
                    "Reasoning model call failed at iteration %s; returning partial answer",
                    iteration,
                )
                if include_progress:
                    progress_events.append(
                        {
                            "iteration": iteration,
                            "status": "synthesizing",
                            "message": "Model call failed, synthesizing from collected evidence...",
                        }
                    )
                result = await self._synthesize_partial_answer(iteration)
                return {
                    "completed": True,
                    "result": result,
                    "progress_events": progress_events,
                }
            raise

        if response.stop_reason == "end_turn":
            text_content = next(
                (block.text for block in response.content if block.type == "text"),
                None,
            )

            if text_content:
                if include_progress:
                    progress_events.append(
                        {
                            "iteration": iteration,
                            "status": "verifying",
                            "message": "Verifying citations...",
                        }
                    )
                result = await self._verify_and_finalize(
                    text_content,
                    self.tool_handler.evidence_log,
                    iteration,
                )
                return {
                    "completed": True,
                    "result": result,
                    "progress_events": progress_events,
                }

        assistant_content = []
        tool_results = []

        for block in response.content:
            if block.type == "text":
                assistant_content.append(block)
            elif block.type == "tool_use":
                tool_key = (block.name, self._tool_input_hash(block.name, block.input))
                current_count = self._tool_call_counts.get(tool_key, 0)
                if current_count >= 2:
                    assistant_content.append(block)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": self._get_redundant_tool_message(),
                        }
                    )
                    continue

                self._tool_call_counts[tool_key] = current_count + 1

                if include_progress:
                    progress_events.append(
                        {
                            "iteration": iteration,
                            "tool": block.name,
                            "status": "executing",
                            "message": f"Executing {block.name}...",
                        }
                    )

                result = await self.tool_handler.execute(
                    block.name,
                    block.input,
                )

                assistant_content.append(block)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    }
                )

        if assistant_content:
            messages.append({"role": "assistant", "content": assistant_content})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        return {
            "completed": False,
            "result": None,
            "progress_events": progress_events,
        }

    async def _create_reasoning_response(self, system_prompt: str, messages: list[dict]) -> Any:
        """Call Anthropic with model fallback for retired/unavailable model IDs."""
        ordered_models = [
            self._active_reasoning_model,
            *[m for m in self._model_candidates if m != self._active_reasoning_model],
        ]

        last_error: Exception | None = None

        for index, model_name in enumerate(ordered_models):
            try:
                response_or_coro = self.client.messages.create(
                    model=model_name,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )
                response = (
                    await response_or_coro
                    if isawaitable(response_or_coro)
                    else response_or_coro
                )
                if model_name != self._active_reasoning_model:
                    logger.warning(
                        "Reasoning model '%s' unavailable; switched to '%s'",
                        self._active_reasoning_model,
                        model_name,
                    )
                    self._active_reasoning_model = model_name
                return response
            except Exception as exc:  # noqa: BLE001 - preserve provider-specific error payloads
                if _is_model_not_found_error(exc):
                    last_error = exc
                    if index < len(ordered_models) - 1:
                        logger.warning(
                            "Reasoning model '%s' not found; trying fallback model.",
                            model_name,
                        )
                        continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("Unable to call reasoning model")

    async def _load_toc_corpus(self, doc_ids: list[str] | None = None) -> str:
        """Load ToC JSON for all relevant documents.

        Args:
            doc_ids: Optional list of documents to load (None = all)

        Returns:
            Formatted string of ToC data for system prompt
        """
        from app.storage.repositories import DocumentRepository

        doc_repo = DocumentRepository(self.db)

        if doc_ids:
            docs = [await doc_repo.get_by_id(doc_id) for doc_id in doc_ids]
            docs = [d for d in docs if d is not None]
        else:
            docs = await doc_repo.list_documents()

        # Format ToC corpus
        toc_entries = []
        for doc in docs:
            try:
                toc_text = self._format_toc_tree(doc.toc_json)
            except Exception:
                logger.warning("Skipping malformed toc_json for document %s", doc.doc_id)
                toc_text = "[Table of contents unavailable — parse error]"
            safe_doc_id = xml_escape(str(doc.doc_id or "unknown"))
            safe_title = xml_escape(str(doc.title or "Untitled"))
            safe_language = xml_escape(str(doc.language or "unknown"))
            safe_summary = xml_escape(str(doc.summary or "No summary available"))
            toc_entries.append(
                "\n".join(
                    [
                        f'<document doc_id="{safe_doc_id}" title="{safe_title}">',
                        f"  <language>{safe_language}</language>",
                        f"  <summary>{safe_summary}</summary>",
                        "  <table_of_contents>",
                        toc_text,
                        "  </table_of_contents>",
                        "</document>",
                    ]
                )
            )

        return "\n---\n".join(toc_entries) if toc_entries else "No documents available."

    def _format_toc_tree(self, toc_node: dict | list | None, indent: int = 0) -> str:
        """Recursively format ToC tree for display.

        Args:
            toc_node: ToC node dictionary or list of nodes
            indent: Current indentation level

        Returns:
            Formatted ToC string
        """
        if toc_node is None:
            return ""
        if isinstance(toc_node, list):
            return "\n".join(self._format_toc_tree(node, indent) for node in toc_node)

        prefix = "  " * indent
        safe_title = xml_escape(str(toc_node.get("title", "Untitled")))
        safe_node_id = xml_escape(str(toc_node.get("node_id", "unknown")))
        lines = [f"{prefix}- {safe_title} ({safe_node_id})"]

        if toc_node.get('summary'):
            lines.append(f"{prefix}  Summary: {xml_escape(str(toc_node['summary']))}")

        if toc_node.get('sub_nodes'):
            for sub_node in toc_node['sub_nodes']:
                lines.append(self._format_toc_tree(sub_node, indent + 1))

        return "\n".join(lines)

    async def _verify_and_finalize(
        self,
        answer: str,
        evidence_log: list[dict],
        iterations: int,
    ) -> dict:
        """Verify citations and finalize answer.

        Args:
            answer: Raw answer text from Claude
            evidence_log: List of evidence items collected
            iterations: Number of iterations used

        Returns:
            Finalized response dictionary
        """
        await self.tool_handler.enrich_evidence_log()

        # Extract citations from answer
        citations = self.evidence_verifier.extract_citations(answer)

        # Verify citations against evidence log
        verified, unverified = self.evidence_verifier.verify(citations, evidence_log)
        answer_text = answer

        if citations and not evidence_log:
            answer_text = (
                "⚠️ Unverifiable answer: citations are present but no evidence was "
                "recorded from retrieval steps.\n\n"
            ) + answer

        if unverified:
            # Log warning but proceed (could implement regeneration here)
            logger.warning("Unverified citations detected: %s", len(unverified))

        # Calculate confidence
        confidence_result = calculate_confidence(evidence_log, verified)

        return {
            "answer": answer_text,
            "confidence": confidence_result["level"],
            "confidence_statement": confidence_result["statement"],
            "citations": verified,
            "evidence_log": evidence_log,
            "sections_explored": list(self.tool_handler.visited_sections),
            "iterations": iterations,
        }

    async def _synthesize_partial_answer(self, iterations: int) -> dict:
        """Synthesize answer when max iterations reached.

        Args:
            iterations: Number of iterations used

        Returns:
            Partial answer response dictionary
        """
        evidence_log = self.tool_handler.evidence_log

        if not evidence_log:
            answer = "I was unable to find relevant information to answer this question within the available documents."
            confidence_result = {"level": "low", "statement": "Confidence: Low - no evidence found"}
        else:
            # Construct partial answer from evidence
            answer = f"Based on the evidence I gathered (from {len(evidence_log)} sources), I can provide partial information:\n\n"
            answer += "However, I reached the maximum number of search iterations before completing a full answer. "
            answer += "You may want to rephrase the question or ask about a more specific aspect."

            confidence_result = calculate_confidence(evidence_log, [])

        return {
            "answer": answer,
            "confidence": confidence_result["level"],
            "confidence_statement": confidence_result["statement"] + " (max iterations reached)",
            "citations": [],
            "evidence_log": evidence_log,
            "sections_explored": list(self.tool_handler.visited_sections),
            "iterations": iterations,
        }
