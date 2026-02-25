"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================


class QueryRequest(BaseModel):
    """Request schema for submitting a question."""

    question: str = Field(..., description="Question to answer")
    doc_ids: list[str] | None = Field(
        default=None,
        description="Optional list of document IDs to search within. If None, searches all documents.",
    )

    @field_validator("doc_ids", mode="before")
    @classmethod
    def normalize_doc_ids(cls, v: Any) -> list[str] | None:
        """Accept list payloads and gracefully coerce scalar form inputs."""
        if v is None:
            return None
        if isinstance(v, str):
            value = v.strip()
            if not value:
                return None
            return [value]
        if isinstance(v, tuple):
            v = list(v)
        if isinstance(v, list):
            normalized = [str(item).strip() for item in v if str(item).strip()]
            return normalized or None
        raise ValueError("doc_ids must be a list of document ids")


class FeedbackRequest(BaseModel):
    """Request schema for user feedback on query results."""

    rating: str = Field(..., description="User rating: thumbs_up or thumbs_down")
    category: str | None = Field(
        default=None,
        description="Feedback category: wrong_answer, incomplete, bad_citation, other",
    )
    details: str | None = Field(
        default=None,
        description="Optional detailed feedback from user",
    )

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: str) -> str:
        """Validate rating is one of the allowed values."""
        allowed = ["thumbs_up", "thumbs_down", "positive", "negative"]
        if v not in allowed:
            raise ValueError(f"Rating must be one of {allowed}")
        if v == "positive":
            return "thumbs_up"
        if v == "negative":
            return "thumbs_down"
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        """Validate category if provided."""
        if v is None:
            return v
        allowed = ["wrong_answer", "incomplete", "bad_citation", "other", "helpful"]
        if v not in allowed:
            raise ValueError(f"Category must be one of {allowed}")
        return v


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================


class Citation(BaseModel):
    """Citation reference to a source paragraph."""

    para_id: str = Field(..., description="Paragraph ID (doc_id:section_id:p001)")
    doc_title: str = Field(..., description="Title of source document")
    section: str = Field(..., description="Section title or path")
    page: int | None = Field(default=None, description="Page number in original document")
    text_snippet: str = Field(..., description="Relevant text excerpt from paragraph")
    original_url: str | None = Field(
        default=None,
        description="Link to original document if available",
    )


class QueryResponse(BaseModel):
    """Complete response for a query including answer and metadata."""

    query_id: str = Field(..., description="Unique query identifier")
    answer: str = Field(..., description="Natural language answer to the question")
    confidence: str = Field(..., description="Confidence level: high, medium, or low")
    confidence_statement: str = Field(
        ...,
        description="Human-readable explanation of confidence level",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="List of citations supporting the answer",
    )
    gaps: str | None = Field(
        default=None,
        description="Description of information gaps if answer is incomplete",
    )
    sections_explored: list[str] = Field(
        default_factory=list,
        description="List of section IDs explored during reasoning",
    )
    iterations: int = Field(..., description="Number of reasoning iterations performed")
    latency_breakdown: dict[str, Any] = Field(
        default_factory=dict,
        description="Timing breakdown for different stages of processing",
    )


class ProgressEvent(BaseModel):
    """Progress event emitted during query processing."""

    iteration: int = Field(..., description="Current iteration number")
    tool: str = Field(..., description="Tool being executed")
    status: str = Field(..., description="Status: started, completed, or failed")


class DocumentInfo(BaseModel):
    """Document metadata for listing and display."""

    doc_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    language: str = Field(..., description="Document language (de, fr, it, en)")
    page_count: int = Field(..., description="Total number of pages")
    file_type: str = Field(..., description="File type: pdf, docx, or pptx")
    uploaded_at: datetime = Field(..., description="Upload timestamp")


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload."""

    doc_id: str = Field(..., description="Unique document identifier")
    status: str = Field(..., description="Upload status: success, processing, or failed")
    filename: str = Field(..., description="Original filename")


# ============================================================================
# ADMIN/UTILITY SCHEMAS (Phase 3)
# ============================================================================


class CacheStats(BaseModel):
    """Cache statistics for monitoring."""

    l1_ingestion_size: int = Field(..., description="L1 cache entry count")
    l2_toc_size: int = Field(..., description="L2 ToC corpus document count")
    l3_embeddings_size: int | None = Field(
        default=None,
        description="L3 embedding count (Phase 2)",
    )
    l4_query_size: int = Field(..., description="L4 query cache entry count")
    l5_trace_size: int = Field(..., description="L5 reasoning trace count")
    l4_hit_rate: float = Field(..., description="L4 cache hit rate (0.0-1.0)")


class ConfigUpdate(BaseModel):
    """Request schema for runtime configuration updates."""

    max_reasoning_iterations: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="Maximum reasoning iterations",
    )
    query_timeout_seconds: int | None = Field(
        default=None,
        ge=10,
        le=300,
        description="Query timeout in seconds",
    )
    log_level: str | None = Field(
        default=None,
        description="Logging level: DEBUG, INFO, WARNING, ERROR",
    )
    dry_run_cache_only: bool | None = Field(
        default=None,
        description="If true, only cached (L4) query results are allowed",
    )
    query_cache_ttl_seconds: int | None = Field(
        default=None,
        ge=30,
        le=604800,
        description="TTL for L4 query cache entries in seconds",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str | None) -> str | None:
        """Validate log level if provided."""
        if v is None:
            return v
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()
