"""Cross-reference extraction with multilingual pattern support."""

import re
from typing import Any


class CrossReferenceExtractor:
    """
    Extract cross-references from text using multilingual patterns.

    Supports German, French, Italian, and English reference patterns for:
    - Section references (e.g., "see Section 3.2", "siehe Abschnitt 4")
    - Appendix references (e.g., "gemäss Anhang A", "selon Annexe B")
    - Document references (e.g., "refer to Security Policy", "verweist auf Richtlinie")
    """

    # Multilingual reference patterns
    PATTERNS = [
        # Section references
        # English: "see Section 3.2", "refer to Section 4.1"
        r"(?:see|refer to)\s+(?:Section|section)\s+(\d+(?:\.\d+)*)",

        # German: "siehe Abschnitt 3.2", "verweist auf Abschnitt 4"
        r"(?:siehe|verweist auf)\s+(?:Abschnitt|abschnitt)\s+(\d+(?:\.\d+)*)",

        # French: "voir chapitre 3.2", "se référer à chapitre 4"
        r"(?:voir|se référer à)\s+(?:chapitre|Chapitre|section|Section)\s+(\d+(?:\.\d+)*)",

        # Italian: "vedi sezione 3.2", "vedere sezione 4"
        r"(?:vedi|vedere)\s+(?:sezione|Sezione)\s+(\d+(?:\.\d+)*)",

        # Appendix references
        # English: "see Appendix A", "refer to Appendix B"
        r"(?:see|refer to)\s+(?:Appendix|appendix)\s+([A-Z])",

        # German: "siehe Anhang A", "gemäss Anhang B"
        r"(?:siehe|gemäss|gemäß|laut)\s+(?:Anhang|anhang)\s+([A-Z])",

        # French: "voir Annexe A", "selon Annexe B"
        r"(?:voir|selon)\s+(?:Annexe|annexe)\s+([A-Z])",

        # Italian: "vedi Allegato A", "secondo Allegato B"
        r"(?:vedi|secondo)\s+(?:Allegato|allegato)\s+([A-Z])",

        # Document/Policy references
        # English: "refer to Security Policy", "see Data Protection Guideline"
        r"(?:refer to|see|according to)\s+([^.\n]{1,100}(?:Policy|policy|Guideline|guideline|Document|document))",

        # German: "gemäss Sicherheitsrichtlinie", "siehe Datenschutzrichtlinie"
        r"(?:gemäss|gemäß|laut|siehe)\s+([^.\n]{1,100}(?:Richtlinie|richtlinie|Dokument|dokument))",

        # French: "selon Politique", "voir Directive"
        r"(?:selon|voir)\s+([^.\n]{1,100}(?:Politique|politique|Directive|directive))",

        # Italian: "secondo Politica", "vedi Direttiva"
        r"(?:secondo|vedi)\s+([^.\n]{1,100}(?:Politica|politica|Direttiva|direttiva))",
    ]

    def __init__(self) -> None:
        """Initialize with compiled regex patterns."""
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.PATTERNS
        ]

    def extract(self, text: str) -> list[dict[str, Any]]:
        """
        Extract cross-references from text.

        Args:
            text: Text content to search for cross-references

        Returns:
            List of dicts with:
                - source_text: Full matched reference text
                - target_hint: Extracted section number, appendix letter, or document name

        Note:
            - Case-insensitive matching
            - Deduplicates identical references
            - Returns empty list if no references found
        """
        references: list[dict[str, Any]] = []
        seen_refs: set[str] = set()  # Track seen references for deduplication

        for pattern in self.compiled_patterns:
            for match in pattern.finditer(text):
                source_text = match.group(0)
                target_hint = match.group(1) if len(match.groups()) > 0 else ""

                # Deduplicate based on source text
                ref_key = source_text.lower()
                if ref_key in seen_refs:
                    continue

                seen_refs.add(ref_key)
                references.append({
                    "source_text": source_text,
                    "target_hint": target_hint.strip(),
                })

        return references
