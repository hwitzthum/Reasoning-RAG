"""Helpers for locating original uploaded source files."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.config import settings
from app.storage.models import Document


def _candidate_doc_dirs(document: Document, documents_root: Path) -> list[Path]:
    """Return candidate folders where the document's source file may exist."""
    candidates: list[Path] = []
    seen: set[str] = set()

    labels: list[str | None] = [document.doc_id, document.title]
    if document.original_filename:
        labels.append(Path(document.original_filename).stem)

    for label in labels:
        if not label:
            continue
        normalized = str(label).strip()
        if not normalized:
            continue
        candidate = documents_root / normalized
        key = str(candidate)
        if key in seen:
            continue
        candidates.append(candidate)
        seen.add(key)

    return candidates


def _sha256(path: Path) -> str | None:
    """Calculate SHA-256 for a file, returning None if unreadable."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def resolve_original_file(
    document: Document,
    documents_path: Path | None = None,
) -> Path | None:
    """Resolve the most likely source file path for a stored document.

    Supports both current layout (`documents/{doc_id}/original.*`) and legacy
    mismatches where `doc_id` diverged from the physical folder name.
    """
    root = Path(documents_path or settings.documents_path)
    if not root.exists():
        return None

    # Preferred lookup: direct folder candidates.
    for doc_dir in _candidate_doc_dirs(document, root):
        if not doc_dir.exists():
            continue

        source_candidates = sorted(doc_dir.glob("original.*"))
        if source_candidates:
            return source_candidates[0]

        # Defensive: allow exact original filename when present.
        if document.original_filename:
            exact_path = doc_dir / document.original_filename
            if exact_path.exists() and exact_path.is_file():
                return exact_path

    # Legacy fallback: hash-match among all original.* files.
    if not document.file_hash:
        return None

    for source_path in sorted(root.glob("*/original.*")):
        if not source_path.is_file():
            continue
        if _sha256(source_path) == document.file_hash:
            return source_path

    return None
