"""Document management API routes."""

import asyncio
import logging
import mimetypes
import re
import shutil
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.document_files import resolve_original_file
from app.api.schemas import DocumentInfo, DocumentUploadResponse
from app.storage.database import get_db
from app.storage.repositories import DocumentRepository
from app.storage.cache import CacheManager
from app.ingestion.pipeline import IngestionPipeline
from app.config import settings

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/documents")


# Allowed file extensions and MIME types
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _build_doc_id(filename: str) -> str:
    """Derive a stable, URL-safe document identifier from a filename."""
    stem = Path(filename).stem.strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "-", stem).strip("-_")
    if not slug:
        slug = f"doc-{uuid4().hex[:8]}"
    return slug[:64]


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Upload a document for ingestion and indexing.

    Accepts PDF, DOCX, or PPTX files, validates them, and initiates the ingestion
    pipeline. The document is parsed, analyzed for structure, annotated with summaries,
    and indexed for retrieval.

    Args:
        file: Uploaded file (PDF, DOCX, or PPTX)
        db: Database session dependency

    Returns:
        DocumentUploadResponse: Contains doc_id, status, and filename

    Raises:
        HTTPException: 400 if file type is invalid
        HTTPException: 500 if ingestion fails
    """
    # Validate file extension
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Validate MIME type if available
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid MIME type: {file.content_type}. Expected one of: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    # Generate doc_id from filename (bounded to DB model length)
    doc_id = _build_doc_id(file.filename)
    existing_doc = await DocumentRepository(db).get_by_id(doc_id)
    if existing_doc is not None:
        logger.warning(
            "Document ID collision detected for upload '%s' -> '%s' (existing title='%s', existing filename='%s')",
            file.filename,
            doc_id,
            existing_doc.title,
            existing_doc.original_filename,
        )

    # Create document directory
    doc_dir = Path(settings.documents_path) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    file_path = doc_dir / f"original{file_ext}"

    try:
        # Write file to disk
        with file_path.open("wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"File saved: {file_path}")

        # Run ingestion pipeline
        pipeline = IngestionPipeline(db)

        # Progress callback for logging
        def progress_callback(stage: str, progress: float):
            logger.info(f"[{doc_id}] {stage}: {progress:.0%}")

        # Ingest document with bounded runtime to avoid indefinite hangs.
        ingested_doc_id = await asyncio.wait_for(
            pipeline.ingest_document(
                file_path,
                doc_id=doc_id,
                progress_callback=progress_callback,
            ),
            timeout=settings.ingestion_timeout_seconds,
        )

        logger.info(f"Document ingestion complete: {ingested_doc_id}")

        # Preserve user-facing filename/title metadata post-ingestion.
        document = await DocumentRepository(db).get_by_id(ingested_doc_id)
        if document is not None:
            document.original_filename = file.filename
            if document.title.lower() in {"original", "untitled"}:
                document.title = Path(file.filename).stem
            await db.commit()
        CacheManager(db).invalidate_toc_corpus()

        return DocumentUploadResponse(
            doc_id=ingested_doc_id,
            status="completed",
            filename=file.filename,
        )

    except asyncio.TimeoutError:
        logger.error("Ingestion timed out for %s after %ss", doc_id, settings.ingestion_timeout_seconds)

        # Remove saved file
        if file_path.exists():
            file_path.unlink()

        # Remove directory if empty
        if doc_dir.exists() and not any(doc_dir.iterdir()):
            doc_dir.rmdir()

        raise HTTPException(
            status_code=504,
            detail=(
                f"Document ingestion timed out after {settings.ingestion_timeout_seconds} seconds. "
                "Try a smaller document or retry later."
            ),
        )

    except Exception as e:
        # Cleanup on failure
        logger.exception(f"Ingestion failed for {doc_id}")

        # Remove saved file
        if file_path.exists():
            file_path.unlink()

        # Remove directory if empty
        if doc_dir.exists() and not any(doc_dir.iterdir()):
            doc_dir.rmdir()

        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {str(e)}",
        )


@router.get("", response_model=list[DocumentInfo])
@router.get("/", response_model=list[DocumentInfo], include_in_schema=False)
async def list_documents(
    db: AsyncSession = Depends(get_db),
) -> list[DocumentInfo]:
    """
    List all documents in the system.

    Returns metadata for all ingested documents including title, language,
    page count, and upload timestamp.

    Args:
        db: Database session dependency

    Returns:
        list[DocumentInfo]: List of document metadata
    """
    # Query all documents
    doc_repo = DocumentRepository(db)
    documents = await doc_repo.list_documents()

    # Map to DocumentInfo schema
    return [
        DocumentInfo(
            doc_id=doc.doc_id,
            title=doc.title,
            file_type=doc.file_type,
            page_count=doc.total_pages,
            language=doc.language,
            summary=doc.summary,
            uploaded_at=doc.created_at,
        )
        for doc in documents
    ]


@router.get("/{doc_id}", response_model=dict)
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get detailed information about a specific document.

    Returns complete document metadata including the full Table of Contents (ToC)
    structure, summary, and all metadata fields.

    Args:
        doc_id: Unique document identifier
        db: Database session dependency

    Returns:
        dict: Document details including ToC JSON

    Raises:
        HTTPException: 404 if document not found
    """
    # Query document
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(doc_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found",
        )

    # Return document with ToC
    return {
        "doc_id": document.doc_id,
        "title": document.title,
        "file_type": document.file_type,
        "page_count": document.total_pages,
        "language": document.language,
        "summary": document.summary,
        "uploaded_at": document.created_at.isoformat() if document.created_at else None,
        "toc": document.toc_json,
    }


@router.get("/{doc_id}/original")
async def get_original_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Download/open the original uploaded source file for a document.

    Args:
        doc_id: Unique document identifier
        db: Database session dependency

    Returns:
        FileResponse for the original file

    Raises:
        HTTPException: 404 if document or original file is missing
    """
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    file_path = resolve_original_file(document)
    if file_path is None:
        raise HTTPException(status_code=404, detail=f"Original file for {doc_id} not found")
    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=document.original_filename or file_path.name,
        content_disposition_type="inline",
    )


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a document and all associated data.

    Removes the document from the database (cascading to sections, paragraphs,
    cross-references, embeddings), invalidates all related caches, and deletes
    files from the filesystem.

    Args:
        doc_id: Unique document identifier
        db: Database session dependency

    Raises:
        HTTPException: 404 if document not found
        HTTPException: 500 if deletion fails
    """
    # Verify document exists
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(doc_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found",
        )

    try:
        # Invalidate caches for this document
        cache_manager = CacheManager(db)
        await cache_manager.invalidate_for_document(doc_id)
        logger.info(f"Invalidated caches for document: {doc_id}")

        # Delete from database (cascades to sections, paragraphs, xrefs)
        await doc_repo.delete(doc_id)
        logger.info(f"Deleted document from database: {doc_id}")
    except Exception as e:
        logger.exception(f"Failed to delete document: {doc_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Document deletion failed: {str(e)}",
        )

    # Best-effort filesystem cleanup should not block successful API deletion.
    doc_dir = Path(settings.documents_path) / doc_id
    if doc_dir.exists():
        try:
            shutil.rmtree(doc_dir)
            logger.info(f"Deleted document directory: {doc_dir}")
        except OSError as e:
            logger.warning(
                "Deleted document '%s' from DB but failed to remove files at %s: %s",
                doc_id,
                doc_dir,
                e,
            )
