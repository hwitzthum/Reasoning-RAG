"""UI routes for Phase 2 web interface."""

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.document_files import resolve_original_file
from app.storage.database import get_db
from app.storage.repositories import DocumentRepository, ParagraphRepository


router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[2] / "ui" / "templates")
)


def _pdf_search_anchor(text: str | None) -> str:
    """Build a PDF search fragment from paragraph text when page numbers are missing."""
    if not text:
        return ""
    words = [part for part in str(text).strip().split() if part]
    if not words:
        return ""
    snippet = " ".join(words[:8])
    return f"#search={quote(snippet)}"


def _build_original_target(document, paragraph) -> str | None:
    """Build the best available URL to open the original source file."""
    if not document:
        return None
    original_file = resolve_original_file(document)
    if original_file is None:
        return None

    target_url = f"/api/documents/{document.doc_id}/original"
    if document.file_type == "pdf" and paragraph.page_number:
        target_url += f"#page={paragraph.page_number}"
    elif document.file_type == "pdf":
        target_url += _pdf_search_anchor(paragraph.text)
    return target_url


@router.get("/ui")
async def query_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Render the main query page."""
    doc_repo = DocumentRepository(db)
    documents = await doc_repo.list_documents()
    return templates.TemplateResponse(
        request=request,
        name="query.html",
        context={
            "documents": documents,
        },
    )


@router.get("/ui/citation/{para_id}")
async def citation_panel(
    para_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Render citation details for side panel."""
    para_repo = ParagraphRepository(db)
    paragraphs = await para_repo.get_by_ids([para_id])
    if not paragraphs:
        raise HTTPException(status_code=404, detail=f"Paragraph {para_id} not found")

    paragraph = paragraphs[0]
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(paragraph.doc_id)
    original_target = _build_original_target(document, paragraph)

    return templates.TemplateResponse(
        request=request,
        name="citation.html",
        context={
            "paragraph": paragraph,
            "document": document,
            "original_url": original_target,
            "original_page_anchor": "",
        },
    )


@router.get("/ui/source/{para_id}")
async def open_source_passage(
    para_id: str,
    request: Request,
    open_original: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Render a focused source passage view, optionally redirecting to original."""
    para_repo = ParagraphRepository(db)
    paragraphs = await para_repo.get_by_ids([para_id])
    if not paragraphs:
        raise HTTPException(status_code=404, detail=f"Paragraph {para_id} not found")

    paragraph = paragraphs[0]
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(paragraph.doc_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document {paragraph.doc_id} not found")

    original_target = _build_original_target(document, paragraph)
    if open_original and original_target:
        return RedirectResponse(url=original_target, status_code=307)

    section_paragraphs = await para_repo.get_by_section(paragraph.doc_id, paragraph.section_id)
    context_before = None
    context_after = None
    for index, candidate in enumerate(section_paragraphs):
        if candidate.para_id != paragraph.para_id:
            continue
        if index > 0:
            context_before = section_paragraphs[index - 1]
        if index + 1 < len(section_paragraphs):
            context_after = section_paragraphs[index + 1]
        break

    return templates.TemplateResponse(
        request=request,
        name="source_passage.html",
        context={
            "paragraph": paragraph,
            "document": document,
            "context_before": context_before,
            "context_after": context_after,
            "open_original_url": (
                f"/ui/source/{para_id}?open_original=true" if original_target else None
            ),
        },
    )


@router.get("/ui/feedback/{query_id}")
async def feedback_partial(query_id: str, request: Request):
    """Render feedback partial for a query."""
    return templates.TemplateResponse(
        request=request,
        name="feedback.html",
        context={"query_id": query_id},
    )
