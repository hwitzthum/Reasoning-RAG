"""Docling parser wrapper for PDF/DOCX/PPTX to Markdown conversion."""

from pathlib import Path
from typing import Any
import magic
from docling.document_converter import DocumentConverter
from docling.datamodel.document import ConversionResult


# Phase 2: Format-specific notes
# DOCX: Docling extracts heading styles from Word styles. Quality depends on proper heading
#       usage in the source document. Embedded images are preserved in markdown.
# PPTX: Slides are mapped to sections. Slide titles become headings, slide content becomes
#       paragraphs. Slide numbers are tracked as page numbers.


class DoclingParser:
    """
    Wrapper for Docling PDF/DOCX/PPTX → Markdown conversion.

    Handles document parsing with unified interface across all supported formats.
    """

    def __init__(self) -> None:
        """Initialize the Docling document converter."""
        self.converter = DocumentConverter()

    async def parse(self, file_path: Path) -> tuple[str, dict[str, Any]]:
        """
        Parse document to Markdown with metadata.

        Args:
            file_path: Path to the document file (PDF, DOCX, or PPTX)

        Returns:
            tuple: (markdown_content, metadata_dict)
                - markdown_content: The document converted to Markdown format
                - metadata_dict: Contains 'title', 'page_count', 'file_type'

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If Docling fails to parse the document
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # Convert document using Docling
            result: ConversionResult = self.converter.convert(str(file_path))

            # Export to Markdown
            markdown = result.document.export_to_markdown()

            # Extract metadata with format-specific handling
            file_type = file_path.suffix[1:].lower()
            metadata = {
                "title": result.document.name or file_path.stem,
                "page_count": self._extract_page_count(result, file_type, file_path),
                "file_type": file_type,
            }

            # Add format-specific metadata
            if file_type == "pptx":
                # For PPTX, page_count represents slide count
                metadata["slide_count"] = metadata["page_count"]

            return markdown, metadata

        except Exception as e:
            raise ValueError(f"Failed to parse document {file_path.name}: {str(e)}") from e

    def _extract_page_count(
        self,
        result: ConversionResult,
        file_type: str,
        file_path: Path,
    ) -> int:
        """
        Extract page/slide count with format-specific handling.

        Args:
            result: Docling conversion result
            file_type: File extension (pdf, docx, pptx)

        Returns:
            int: Page count (or slide count for PPTX)

        Note:
            PPTX: Returns slide count
            DOCX/PDF: Returns page count
        """
        # Try multiple attributes for page/slide count exposed by Docling.
        count = 0
        if hasattr(result.document, 'page_count'):
            count = result.document.page_count or 0
        elif hasattr(result, 'pages'):
            count = len(result.pages)
        elif hasattr(result.document, 'pages'):
            count = len(result.document.pages)

        # Format-specific fallback extraction when Docling metadata is missing.
        if count <= 0 and file_type == "pptx":
            try:
                from pptx import Presentation

                count = len(Presentation(str(file_path)).slides)
            except Exception:
                count = 0

        # DOCX page counts are not directly encoded in OOXML; keep at least 1 page.
        if count <= 0 and file_type == "docx":
            count = 1

        return count


def validate_file(file_path: Path) -> bool:
    """
    Validate file type by extension and MIME type.

    Args:
        file_path: Path to the file to validate

    Returns:
        bool: True if file is valid (PDF, DOCX, or PPTX), False otherwise

    Note:
        This function does not raise exceptions - it returns False for invalid files.
    """
    # Check file extension
    # Note: .md allowed for testing purposes
    allowed_extensions = {".pdf", ".docx", ".pptx", ".md"}
    if file_path.suffix.lower() not in allowed_extensions:
        return False

    # Check if file exists
    if not file_path.exists():
        return False

    # Check MIME type
    allowed_mimes = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/markdown",  # For testing
        "text/plain",  # Markdown may be detected as plain text
    }

    try:
        mime = magic.from_file(str(file_path), mime=True)
        return mime in allowed_mimes
    except Exception:
        # If MIME detection fails, fall back to extension-only validation
        return file_path.suffix.lower() in allowed_extensions
