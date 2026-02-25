"""Markdown structure analysis and paragraph extraction."""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Section:
    """
    Represents a document section extracted from Markdown headings.

    Attributes:
        section_id: Hierarchical ID (e.g., "s1", "s1.1", "s1.1.2")
        title: Section heading text
        heading_level: Markdown heading level (1-6)
        content: Text content under this section
        page_start: Starting page number (if available)
        page_end: Ending page number (if available)
        parent_id: ID of parent section (None for top-level)
        children: List of child sections
    """

    section_id: str
    title: str
    heading_level: int
    content: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    parent_id: Optional[str] = None
    children: list["Section"] = field(default_factory=list)


class MarkdownStructureAnalyzer:
    """
    Parse Markdown heading hierarchy into a section tree.

    Best-effort structure analysis - accepts imperfect heading detection from Docling.
    """

    # Matches Markdown headings: # Title, ## Title, etc.
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def analyze(self, markdown: str) -> list[Section]:
        """
        Extract hierarchical section structure from Markdown.

        Args:
            markdown: Markdown content with heading structure

        Returns:
            List of Section objects in document order (flat list with parent_id links)

        Note:
            If document has no headings, returns a single root section with all content.
        """
        sections: list[Section] = []
        current_stack: list[Section] = []  # Track parent sections at each level
        section_counter = [0] * 6  # Counters for each heading level

        lines = markdown.split("\n")
        current_content: list[str] = []
        current_section: Optional[Section] = None

        for line in lines:
            match = self.HEADING_PATTERN.match(line)
            if match:
                # Save previous section content
                if current_section:
                    current_section.content = "\n".join(current_content).strip()

                level = len(match.group(1))
                title = match.group(2).strip()

                # Generate hierarchical section ID
                section_counter[level - 1] += 1
                # Reset deeper levels
                for i in range(level, 6):
                    section_counter[i] = 0

                section_id = "s" + ".".join(
                    str(section_counter[i])
                    for i in range(level)
                    if section_counter[i] > 0
                )

                # Find parent section
                parent_id = None
                if level > 1 and current_stack:
                    # Find nearest parent with lower heading level
                    for parent in reversed(current_stack):
                        if parent.heading_level < level:
                            parent_id = parent.section_id
                            parent.children.append(section_id)  # Track child ID
                            break

                current_section = Section(
                    section_id=section_id,
                    title=title,
                    heading_level=level,
                    content="",
                    page_start=None,
                    page_end=None,
                    parent_id=parent_id,
                    children=[],
                )

                sections.append(current_section)

                # Update stack - remove sections at same or deeper level
                while current_stack and current_stack[-1].heading_level >= level:
                    current_stack.pop()
                current_stack.append(current_section)

                current_content = []
            else:
                current_content.append(line)

        # Save last section content
        if current_section:
            current_section.content = "\n".join(current_content).strip()

        # Handle documents with no headings - create synthetic root section
        # so structural tools can still navigate the full document body.
        if not sections:
            sections.append(
                Section(
                    section_id="s000",
                    title="Full Document",
                    heading_level=1,
                    content=markdown.strip(),
                    page_start=None,
                    page_end=None,
                    parent_id=None,
                    children=[],
                )
            )

        return sections


@dataclass
class Paragraph:
    """
    Represents a paragraph extracted from section content.

    Attributes:
        para_id: Unique paragraph ID (format: doc_id:section_id:p001)
        text: Plain text content
        section_id: ID of containing section
        para_index: 1-based index within section
        markdown_source: Original markdown text
    """

    para_id: str
    text: str
    section_id: str
    para_index: int
    markdown_source: str


class ParagraphExtractor:
    """
    Extract paragraphs from section content.

    Splits content on double newlines and generates stable paragraph IDs.
    """

    # Split on double newlines (paragraph breaks)
    PARAGRAPH_SPLIT = re.compile(r"\n\n+")

    def extract(self, doc_id: str, sections: list[Section]) -> list[Paragraph]:
        """
        Extract paragraphs from all sections with stable IDs.

        Args:
            doc_id: Document identifier for generating para_ids
            sections: List of sections to extract paragraphs from

        Returns:
            List of Paragraph objects with format: doc_id:section_id:p{index:03d}

        Note:
            - Skips empty paragraphs
            - 1-based indexing within each section
            - Preserves original markdown in markdown_source
        """
        paragraphs: list[Paragraph] = []

        for section in sections:
            if not section.content.strip():
                continue

            # Split content into paragraphs
            raw_paragraphs = self.PARAGRAPH_SPLIT.split(section.content)

            for idx, text in enumerate(raw_paragraphs, start=1):
                text = text.strip()
                if not text:
                    continue

                # Generate stable paragraph ID
                para_id = f"{doc_id}:{section.section_id}:p{idx:03d}"

                paragraphs.append(
                    Paragraph(
                        para_id=para_id,
                        text=text,
                        section_id=section.section_id,
                        para_index=idx,
                        markdown_source=text,  # Store original for reference
                    )
                )

        return paragraphs
