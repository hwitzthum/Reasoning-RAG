"""Section annotation for summaries, language detection, and metadata extraction."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from typing import Any

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    Anthropic,
    AuthenticationError,
)

from app.config import settings

logger = logging.getLogger(__name__)

DEPRECATED_MODEL_ALIASES = {
    # Claude provider warning: these models reached EOL in February 2026.
    "claude-3-5-haiku-20241022": "claude-haiku-4-5-20251001",
    "claude-3-5-haiku-latest": "claude-haiku-4-5-20251001",
}

VALID_LANGUAGES = {"de", "fr", "it", "en"}

LANGUAGE_MARKERS = {
    "de": {
        " und ", " der ", " die ", " das ", " fuer ", " mit ", " nicht ", " gemaess ",
        " richtlinie ", " datenschutz ", " passwort ", " abschnitt ", " schweiz ",
    },
    "fr": {
        " le ", " la ", " les ", " des ", " et ", " pour ", " avec ", " politique ",
        " section ", " conformite ", " donnees ", " suisse ",
    },
    "it": {
        " il ", " lo ", " gli ", " le ", " e ", " per ", " con ", " politica ",
        " sezione ", " sicurezza ", " dati ", " svizzera ",
    },
    "en": {
        " the ", " and ", " with ", " for ", " policy ", " section ", " security ",
        " data ", " password ", " compliance ",
    },
}


class HaikuAnnotator:
    """Generate section summaries and language metadata."""

    def __init__(self) -> None:
        """Initialize the Anthropic client and model settings."""
        api_key = (settings.anthropic_api_key or "").strip()
        key_lower = api_key.lower()

        self.offline_mode = (
            not api_key
            or key_lower.startswith("test")
            or key_lower.startswith("dummy")
            or key_lower.startswith("sk-test")
            or key_lower.startswith("sk-dummy")
            or key_lower in {"changeme", "your-api-key", "your-api-key-here"}
        )
        self.client = None if self.offline_mode else Anthropic(api_key=api_key)

        requested_model = settings.annotation_model
        self.model = DEPRECATED_MODEL_ALIASES.get(requested_model, requested_model)
        if requested_model != self.model:
            logger.warning(
                "annotation_model '%s' is deprecated; using '%s' instead",
                requested_model,
                self.model,
            )

        if self.offline_mode:
            logger.warning(
                "Annotation offline mode active; using heuristic summaries/language detection "
                "because ANTHROPIC_API_KEY is test/dummy or missing."
            )

        self.max_retries = 2
        self.request_timeout_seconds = 20

    async def annotate_section(
        self,
        title: str,
        content: str,
        context: str = "",
    ) -> dict[str, Any]:
        """Generate summary and metadata for a section."""
        if self.offline_mode:
            return self._get_fallback_annotation(title, content)

        truncated_content = content[:3000]

        prompt = f"""Analyze this document section and provide:
1. A concise summary (1-3 sentences based on complexity - simple content gets 1 sentence, complex content gets up to 3)
2. The primary language (de, fr, it, or en)
3. Key topics (3-5 keywords or phrases)
4. Any cross-references to other sections/documents (e.g., "see Section X", "gemaess Anhang Y", "refer to Appendix Z")

Section Title: {title}

{f'Document Context: {context}' if context else ''}

Content:
{truncated_content}

Respond ONLY with valid JSON in this exact format:
{{
    "summary": "...",
    "language": "de|fr|it|en",
    "topics": ["topic1", "topic2", "topic3"],
    "cross_references": ["see Section 3.2", "gemaess Anhang B"]
}}"""

        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.messages.create,
                        model=self.model,
                        max_tokens=500,
                        messages=[{"role": "user", "content": prompt}],
                    ),
                    timeout=self.request_timeout_seconds,
                )

                response_text = response.content[0].text if response.content else "{}"
                result = json.loads(response_text)
                detected_language = result.get("language")
                if detected_language not in VALID_LANGUAGES:
                    detected_language = self._detect_language_heuristic(title, truncated_content)

                summary = (result.get("summary") or "").strip()
                if not summary:
                    summary = self._build_fallback_summary(title, truncated_content)

                topics = result.get("topics") if isinstance(result.get("topics"), list) else []
                if not topics:
                    topics = self._extract_topics(title, truncated_content)

                cross_references = (
                    result.get("cross_references")
                    if isinstance(result.get("cross_references"), list)
                    else []
                )

                return {
                    "summary": summary,
                    "language": detected_language,
                    "topics": topics,
                    "cross_references": cross_references,
                }

            except json.JSONDecodeError:
                if attempt == self.max_retries - 1:
                    return self._get_fallback_annotation(title, truncated_content)

            except AuthenticationError:
                # Auth errors are deterministic and should not be retried repeatedly.
                logger.warning(
                    "Anthropic authentication failed during annotation; falling back to heuristic mode."
                )
                return self._get_fallback_annotation(title, truncated_content)

            except APIStatusError as exc:
                status_code = getattr(exc, "status_code", None)
                if status_code in {400, 401, 403, 404, 422}:
                    logger.warning(
                        "Anthropic API status %s for annotation; using heuristic fallback.",
                        status_code,
                    )
                    return self._get_fallback_annotation(title, truncated_content)
                if attempt == self.max_retries - 1:
                    return self._get_fallback_annotation(title, truncated_content)

            except (APITimeoutError, APIConnectionError, asyncio.TimeoutError):
                if attempt == self.max_retries - 1:
                    return self._get_fallback_annotation(title, truncated_content)

            except Exception:
                if attempt == self.max_retries - 1:
                    logger.exception("Unexpected annotation error; using heuristic fallback.")
                    return self._get_fallback_annotation(title, truncated_content)

        return self._get_fallback_annotation(title, truncated_content)

    def _get_fallback_annotation(self, title: str, content: str) -> dict[str, Any]:
        """Provide local fallback annotation when API calls are unavailable."""
        return {
            "summary": self._build_fallback_summary(title, content),
            "language": self._detect_language_heuristic(title, content),
            "topics": self._extract_topics(title, content),
            "cross_references": [],
        }

    def _build_fallback_summary(self, title: str, content: str) -> str:
        """Build a short deterministic summary without LLM usage."""
        normalized = re.sub(r"\s+", " ", (content or "").strip())
        if normalized:
            first_sentence = re.split(r"(?<=[.!?])\s+", normalized)[0]
            return first_sentence[:220]
        return f"Content related to {title}"

    def _extract_topics(self, title: str, content: str) -> list[str]:
        """Extract lightweight keyword topics from title/content."""
        blob = f"{title} {content}".lower()
        blob = unicodedata.normalize("NFKD", blob)
        blob = "".join(ch for ch in blob if not unicodedata.combining(ch))
        tokens = re.findall(r"[a-zA-Z]{4,}", blob)
        stop = {
            "this", "that", "with", "from", "have", "must", "section", "document",
            "policy", "richtlinie", "diese", "dieser", "pour", "avec", "sono", "della",
        }
        topics: list[str] = []
        for token in tokens:
            if token in stop:
                continue
            if token not in topics:
                topics.append(token)
            if len(topics) >= 5:
                break

        if topics:
            return topics
        return [title] if title else ["general"]

    def _detect_language_heuristic(self, title: str, content: str) -> str:
        """Best-effort language detection when model annotation is unavailable."""
        text = f" {title} {content} ".lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))

        scores = {lang: 0 for lang in VALID_LANGUAGES}
        for lang, markers in LANGUAGE_MARKERS.items():
            for marker in markers:
                scores[lang] += text.count(marker)

        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return "en"
        return best
