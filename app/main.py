"""FastAPI application entry point for Reasoning-RAG.

This module configures and initializes the FastAPI application with all
necessary middleware, routers, and lifecycle hooks.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
import logging
import traceback

from app.storage.database import init_db
from app.api.routes import query, documents, ui, admin
from app.api.exceptions import (
    IngestionError,
    QueryTimeoutError,
    DocumentNotFoundError,
    ValidationError,
)
from app.config import settings
from app.logging_config import configure_logging, get_logger


# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown tasks:
    - Startup: Initialize database, load ToC corpus into cache
    - Shutdown: Cleanup resources if needed
    """
    # Startup
    logger.info("Starting Reasoning-RAG application...")

    # Initialize database
    try:
        await init_db()
        logger.info("✓ Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Load ToC corpus into cache (if using in-memory cache)
    # Note: This will be implemented when cache is fully configured
    logger.info("✓ Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Reasoning-RAG application...")
    # Cleanup tasks if needed
    logger.info("✓ Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Reasoning-RAG",
    description="Reasoning-driven document QA system for Caritas Switzerland",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(admin.router, tags=["admin"])
app.include_router(admin.page_router, tags=["admin-ui"])
app.include_router(ui.router, tags=["ui"])

# Mount static files (for frontend assets)
# Note: static assets live in app/ui/static.
ui_static_dir = Path(__file__).resolve().parent / "ui" / "static"
try:
    app.mount("/static", StaticFiles(directory=str(ui_static_dir)), name="static")
except RuntimeError:
    logger.warning("Static directory not found - skipping static file mounting")


# Global exception handlers
@app.exception_handler(IngestionError)
async def ingestion_error_handler(request: Request, exc: IngestionError):
    """Handle document ingestion errors."""
    logger.error(f"Ingestion error: {exc.message}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Document ingestion failed",
            "detail": exc.message if settings.log_level == "DEBUG" else None,
            "doc_id": exc.doc_id,
        },
    )


@app.exception_handler(QueryTimeoutError)
async def query_timeout_handler(request: Request, exc: QueryTimeoutError):
    """Handle query timeout errors."""
    logger.warning(
        f"Query timeout: {exc.elapsed_seconds}s - {exc.query_id}"
    )
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={
            "error": "Query timed out",
            "detail": f"Query exceeded {exc.elapsed_seconds:.1f} second timeout",
            "query_id": exc.query_id,
        },
    )


@app.exception_handler(DocumentNotFoundError)
async def document_not_found_handler(request: Request, exc: DocumentNotFoundError):
    """Handle document not found errors."""
    logger.info(f"Document not found: {exc.doc_id}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Document not found",
            "detail": f"Document {exc.doc_id} does not exist",
        },
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle custom validation errors."""
    logger.warning(f"Validation error: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation failed",
            "detail": exc.message,
            "field": exc.field,
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic request validation errors."""
    logger.warning(f"Request validation failed: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Request validation failed",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.exception("Unhandled exception occurred")

    # Don't expose internal details in production
    detail = None
    if settings.log_level == "DEBUG":
        detail = {
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": detail,
        },
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status and version info
    """
    return {
        "status": "healthy",
        "service": "reasoning-rag",
        "version": "0.1.0",
    }


# Root endpoint
@app.get("/")
async def root(request: Request):
    """Root endpoint with API information.

    Returns:
        dict: API welcome message and documentation link
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url="/ui", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return {
        "message": "Reasoning-RAG API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
