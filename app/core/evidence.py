"""Evidence tracking and citation verification.

This module implements the three safeguards against hallucinated citations:
1. LLM can only cite para_ids it has actually retrieved
2. Post-generation verification step
3. Quote-matching for direct quotes (fuzzy match for minor LLM paraphrasing)
"""

import re
import logging
from typing import Any
from difflib import SequenceMatcher
from anthropic import AsyncAnthropic  # Backward-compatible symbol for tests/patching

logger = logging.getLogger(__name__)


class EvidenceVerifier:
    """Verify citations and calculate confidence scores.

    This class implements citation extraction from LLM answers, verification
    against the evidence log, and fuzzy quote matching.
    """

    # Citation formats supported:
    # - [Document Title, Section X.Y, p.N]
    # - [Document Title, Abschnitt X.Y.Z Titel]
    # - [Document Title, Kapitel X.Y]
    # - [Document Title, Art. 5], [Document Title, § 3], etc.
    CITATION_PATTERN = re.compile(
        r"\[(?P<doc_title>[^,\]]+),\s*(?P<section_label>(?:Section|Abschnitt|Kapitel|Chapter|Sec\.?|§|Art\.?|Artikel|Punkt|Absatz|Abs\.?|Articolo|Alinéa|Chiffre)\s+[^\],]+?)(?:,\s*(?P<page_label>(?:p\.?|page|s\.?|seite)\s*\d+))?\]",
        re.IGNORECASE,
    )
    PARA_ID_CITATION_PATTERN = re.compile(
        r"\[(?P<para_id>[A-Za-z0-9_-]+:[A-Za-z0-9_.-]+:p\d+)\]"
    )

    def extract_citations(self, answer: str) -> list[dict]:
        """Extract citations from an answer.

        Parses inline citations in common multilingual formats.

        Args:
            answer: The LLM-generated answer text

        Returns:
            List of citation dictionaries with fields:
                - doc_title: Document title
                - section: Section identifier (e.g., "3.2")
                - page: Page number
                - text_snippet: Surrounding text for context
        """
        citations = []

        for match in self.CITATION_PATTERN.finditer(answer):
            doc_title = match.group("doc_title").strip()
            section_label = match.group("section_label").strip()
            section = self._extract_section_number(section_label) or section_label
            page_label = match.group("page_label")
            page = None
            if page_label:
                page_match = re.search(r"(\d+)", page_label)
                if page_match:
                    page = int(page_match.group(1))

            # Extract surrounding text for context (50 chars before/after)
            start = max(0, match.start() - 50)
            end = min(len(answer), match.end() + 50)
            text_snippet = answer[start:end].strip()

            citations.append({
                "doc_title": doc_title,
                "section": section,
                "section_label": section_label,
                "page": page,
                "text_snippet": text_snippet,
                "citation_text": match.group(0),
            })

        # Accept direct para_id citations emitted by some model outputs.
        # Example: [original:s14:p001]
        for match in self.PARA_ID_CITATION_PATTERN.finditer(answer):
            para_id = match.group("para_id").strip()
            parts = para_id.split(":")
            doc_id = parts[0] if parts else ""
            section_id = parts[1] if len(parts) > 1 else ""
            section = self._extract_section_number(section_id) or section_id
            start = max(0, match.start() - 50)
            end = min(len(answer), match.end() + 50)
            text_snippet = answer[start:end].strip()
            citations.append(
                {
                    "doc_title": doc_id or "Document",
                    "section": section,
                    "section_label": section_id or section,
                    "page": None,
                    "text_snippet": text_snippet,
                    "citation_text": match.group(0),
                    "para_id": para_id,
                    "verified_para_id": para_id,
                }
            )

        return citations

    def verify(
        self,
        citations: list[dict],
        evidence_log: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Verify citations against evidence log.

        Each citation must trace back to a para_id that was actually
        retrieved during the reasoning loop.

        Args:
            citations: List of citation dicts from extract_citations()
            evidence_log: List of evidence items with para_id and relevance

        Returns:
            Tuple of (verified_citations, unverified_citations)
        """
        evidence_entries: list[dict[str, Any]] = []
        evidence_doc_ids: set[str] = set()
        for item in evidence_log:
            para_id = item.get("para_id")
            if not isinstance(para_id, str) or ":" not in para_id:
                continue

            parts = para_id.split(":")
            doc_id = item.get("doc_id") or parts[0]
            section_id = item.get("section_id")
            if not section_id and len(parts) >= 2:
                section_id = parts[1]

            entry = {
                "para_id": para_id,
                "doc_id": doc_id,
                "doc_title": item.get("doc_title"),
                "section_id": section_id,
                "section_title": item.get("section_title"),
                "page_number": item.get("page_number"),
            }
            evidence_entries.append(entry)
            if isinstance(doc_id, str):
                evidence_doc_ids.add(doc_id)

        verified = []
        unverified = []

        for citation in citations:
            direct_para_id = citation.get("verified_para_id") or citation.get("para_id")
            if isinstance(direct_para_id, str) and direct_para_id:
                if any(entry.get("para_id") == direct_para_id for entry in evidence_entries):
                    citation["para_id"] = direct_para_id
                    citation["verified_para_id"] = direct_para_id
                    verified.append(citation)
                    continue

            matched_entry = None
            citation_doc_title = str(citation.get("doc_title") or "").strip()
            citation_section = str(citation.get("section") or "").strip()
            citation_section_label = str(citation.get("section_label") or "").strip()
            citation_page = citation.get("page")

            for entry in evidence_entries:
                if not self._doc_title_matches(citation_doc_title, entry):
                    continue

                section_match = False
                section_id = str(entry.get("section_id") or "").strip()
                if citation_section and section_id and self._section_matches(section_id, citation_section):
                    section_match = True

                section_title = str(entry.get("section_title") or "").strip()
                if (
                    not section_match
                    and citation_section_label
                    and section_title
                    and self._section_label_matches(citation_section_label, section_title)
                ):
                    section_match = True

                page_number = entry.get("page_number")
                if (
                    not section_match
                    and isinstance(citation_page, int)
                    and isinstance(page_number, int)
                    and citation_page == page_number
                ):
                    section_match = True

                if section_match:
                    matched_entry = entry
                    break

            if matched_entry is None and len(evidence_doc_ids) == 1 and evidence_entries:
                # Guardrail monitoring: log when previous single-doc fallback path
                # would have accepted this citation without matching evidence.
                logger.warning(
                    "Citation rejected after strict verification (single-doc fallback disabled): %s",
                    citation.get("citation_text") or citation.get("doc_title"),
                )

            if matched_entry is not None:
                citation["para_id"] = matched_entry["para_id"]
                citation["verified_para_id"] = matched_entry["para_id"]
                verified.append(citation)
            else:
                unverified.append(citation)

        return verified, unverified

    def _section_matches(self, section_id: str, citation_section: str) -> bool:
        """Check if a section_id matches a citation section.

        Args:
            section_id: Internal section ID (e.g., "s001.1", "s001", "s002.1")
            citation_section: Citation section number (e.g., "1.1", "1.0", "2.1")

        Returns:
            True if they refer to the same section
        """
        citation_number = self._extract_section_number(citation_section) or citation_section
        normalized_id = self._normalize_section_token(section_id.lstrip("s"))
        normalized_citation = self._normalize_section_token(citation_number)
        if not normalized_id or not normalized_citation:
            return False
        if normalized_id == normalized_citation:
            return True
        return normalized_citation.endswith(".0") and normalized_id == normalized_citation[:-2]

    def _normalize_section_token(self, value: str) -> str:
        """Normalize section tokens by removing leading zeros per numeric part."""
        token = str(value or "").strip()
        if not token:
            return ""
        parts = token.split(".")
        normalized_parts = []
        for part in parts:
            cleaned = part.strip()
            if cleaned.isdigit():
                normalized_parts.append(str(int(cleaned)))
            else:
                normalized_parts.append(cleaned.lstrip("0") or "0")
        return ".".join(normalized_parts)

    def _extract_section_number(self, text: str) -> str | None:
        """Extract numeric section notation from a text snippet."""
        match = re.search(r"(\d+(?:\.\d+)*)", str(text or ""))
        return match.group(1) if match else None

    def _normalize_text(self, value: str) -> str:
        """Lowercase text with collapsed whitespace for fuzzy comparisons."""
        return re.sub(r"\s+", " ", str(value or "")).strip().lower()

    def _section_label_matches(self, citation_label: str, section_title: str) -> bool:
        """Match localized citation labels against section titles."""
        left = self._normalize_text(citation_label)
        right = self._normalize_text(section_title)
        if not left or not right:
            return False
        if left in right or right in left:
            return True

        left_num = self._extract_section_number(left)
        right_num = self._extract_section_number(right)
        if left_num and right_num:
            return self._normalize_section_token(left_num) == self._normalize_section_token(right_num)
        return False

    def _doc_title_matches(self, citation_doc_title: str, evidence_entry: dict[str, Any]) -> bool:
        """Check if citation doc title is compatible with an evidence entry."""
        citation = self._normalize_text(citation_doc_title)
        if not citation:
            return True

        entry_title = self._normalize_text(str(evidence_entry.get("doc_title") or ""))
        entry_doc_id = self._normalize_text(str(evidence_entry.get("doc_id") or ""))

        if entry_title in {"original", "untitled", "document"}:
            # Treat placeholder titles as unknown metadata.
            return True

        if entry_title and (citation == entry_title or citation in entry_title or entry_title in citation):
            return True
        if entry_doc_id and (citation == entry_doc_id or citation in entry_doc_id or entry_doc_id in citation):
            return True
        # If we don't have title metadata for this evidence, don't hard-fail here.
        return not entry_title

    def match_quotes(self, quote: str, evidence_texts: list[str]) -> bool:
        """Fuzzy match a quote against evidence texts.

        Uses sequence matching with 85% threshold to allow for minor
        LLM paraphrasing while catching exact quotes.

        Args:
            quote: The quoted text to verify
            evidence_texts: List of paragraph texts from evidence log

        Returns:
            True if quote matches any evidence text above threshold
        """
        threshold = 0.85

        for evidence_text in evidence_texts:
            # Use SequenceMatcher for fuzzy comparison
            ratio = SequenceMatcher(None, quote.lower(), evidence_text.lower()).ratio()
            if ratio >= threshold:
                return True

            # Also check if quote is a substring (for exact partial quotes)
            if quote.lower() in evidence_text.lower():
                return True

        return False


def calculate_confidence(evidence_log: list[dict], citations: list[dict]) -> dict:
    """Calculate confidence level based on evidence quality.

    Calibration notes (Phase 3):
    - Evidence diversity matters: answers backed by multiple documents are more reliable.
    - Evidence depth matters: repeated evidence from one source can still be weak.
    - Unanswered cross-references reduce confidence.
    - Single-source answers are capped at medium confidence.

    Args:
        evidence_log: List of evidence items recorded during reasoning
        citations: List of extracted citations

    Returns:
        Dictionary with:
            - level: "high", "medium", or "low"
            - statement: Human-readable confidence statement
    """
    evidence_count = len(evidence_log)
    citation_count = len(citations)

    # Evidence diversity: unique source documents represented in evidence para_ids.
    source_docs = set()
    for item in evidence_log:
        para_id = item.get("para_id")
        if isinstance(para_id, str) and ":" in para_id:
            source_docs.add(para_id.split(":", 1)[0])
    evidence_diversity = len(source_docs)

    # Evidence depth: average evidence items per source document.
    evidence_depth = (evidence_count / evidence_diversity) if evidence_diversity > 0 else 0.0

    # Unanswered cross-reference penalty signal.
    unresolved_cross_refs = sum(
        1
        for item in evidence_log
        if item.get("unresolved_cross_reference") or item.get("cross_ref_unresolved")
    )

    if evidence_count == 0:
        return {
            "level": "low",
            "statement": (
                "Confidence: Low - no supporting evidence found "
                "(diversity=0, depth=0.00, unresolved_xrefs=0)"
            ),
            "metrics": {
                "evidence_diversity": 0,
                "evidence_depth": 0.0,
                "unresolved_cross_references": 0,
            },
        }

    score = 0
    if evidence_count >= 3:
        score += 2
    elif evidence_count >= 1:
        score += 1

    if citation_count >= 2:
        score += 2
    elif citation_count >= 1:
        score += 1

    if evidence_diversity >= 2:
        score += 2
    elif evidence_diversity == 1:
        score += 1

    if evidence_depth >= 1.5:
        score += 1

    if unresolved_cross_refs > 0:
        score -= 1

    if score >= 6:
        level = "high"
    elif score >= 3:
        level = "medium"
    else:
        level = "low"

    # Single-source answers remain medium max even with high raw score.
    if level == "high" and evidence_diversity <= 1:
        level = "medium"

    descriptors = {
        "high": "direct multi-source evidence with strong citation backing",
        "medium": "partially supported evidence with moderate certainty",
        "low": "limited or weakly corroborated evidence",
    }
    return {
        "level": level,
        "statement": (
            f"Confidence: {level.capitalize()} - {descriptors[level]} "
            f"(diversity={evidence_diversity}, depth={evidence_depth:.2f}, "
            f"unresolved_xrefs={unresolved_cross_refs})"
        ),
        "metrics": {
            "evidence_diversity": evidence_diversity,
            "evidence_depth": round(evidence_depth, 3),
            "unresolved_cross_references": unresolved_cross_refs,
        },
    }
