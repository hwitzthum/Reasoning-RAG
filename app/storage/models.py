"""SQLAlchemy ORM models for the Reasoning-RAG system."""

from datetime import UTC, datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Index,
    LargeBinary,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


def utc_now_naive() -> datetime:
    """Return current UTC time as naive datetime for legacy DB columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class Document(Base):
    """Stored documents with metadata."""

    __tablename__ = "documents"

    doc_id = Column(String(255), primary_key=True)
    title = Column(String(500), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf, docx, pptx
    language = Column(String(5), nullable=False)  # de, fr, it, en
    total_pages = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256
    toc_json = Column(JSON, nullable=False)  # Full ToC tree
    summary = Column(Text)  # Document-level summary
    original_filename = Column(String(500))
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    # Relationships
    sections = relationship("Section", back_populates="document", cascade="all, delete-orphan")
    paragraphs = relationship("Paragraph", back_populates="document", cascade="all, delete-orphan")


class Section(Base):
    """Document sections (ToC nodes)."""

    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(String(50), nullable=False)  # e.g., "s001.1"
    doc_id = Column(String(255), ForeignKey("documents.doc_id", ondelete="CASCADE"))
    parent_section_id = Column(String(50))  # For hierarchy
    title = Column(String(500), nullable=False)
    summary = Column(Text)  # Haiku-generated
    page_start = Column(Integer)
    page_end = Column(Integer)
    heading_level = Column(Integer)  # 1, 2, 3
    section_path = Column(JSON)  # ["1. Intro", "1.1 Scope"]

    # Relationships
    document = relationship("Document", back_populates="sections")

    __table_args__ = (
        Index("ix_sections_doc_section", "doc_id", "section_id", unique=True),
    )


class Paragraph(Base):
    """Individual paragraphs with full provenance."""

    __tablename__ = "paragraphs"

    para_id = Column(String(100), primary_key=True)  # doc_id:section_id:p001
    doc_id = Column(String(255), ForeignKey("documents.doc_id", ondelete="CASCADE"))
    section_id = Column(String(50), nullable=False)
    para_index = Column(Integer, nullable=False)  # 1-based
    text = Column(Text, nullable=False)
    markdown_source = Column(Text)  # Original markdown
    page_number = Column(Integer)  # PDF physical page
    section_path = Column(JSON)  # ["1. Intro", "1.1 Scope"]

    # Relationships
    document = relationship("Document", back_populates="paragraphs")
    embeddings = relationship("Embedding", back_populates="paragraph", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_paragraphs_doc_section", "doc_id", "section_id"),
        Index("ix_paragraphs_text_fts", "text"),  # For grep_documents
    )


class CrossReference(Base):
    """Cross-reference index between sections/documents."""

    __tablename__ = "cross_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_para_id = Column(String(100), ForeignKey("paragraphs.para_id", ondelete="CASCADE"))
    source_text = Column(Text, nullable=False)  # "see Appendix G"
    target_doc_id = Column(String(255))  # Resolved target
    target_node_id = Column(String(50))  # Resolved section
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now_naive)

    __table_args__ = (
        Index("ix_crossref_source", "source_para_id"),
        Index("ix_crossref_target", "target_doc_id", "target_node_id"),
    )


class QueryCache(Base):
    """L4: Query result cache."""

    __tablename__ = "query_cache"

    query_hash = Column(String(64), primary_key=True)  # SHA-256 of query + doc_scope
    query_text = Column(Text, nullable=False)
    doc_scope = Column(JSON)  # List of doc_ids or null
    answer = Column(Text, nullable=False)
    confidence = Column(String(10))  # high, medium, low
    citations = Column(JSON, nullable=False)
    cited_doc_ids = Column(JSON)  # Normalized list of cited doc_ids for SQL-side invalidation
    evidence_log = Column(JSON)
    sections_explored = Column(JSON)
    iterations = Column(Integer)
    created_at = Column(DateTime, default=utc_now_naive)

    __table_args__ = (Index("ix_query_cache_created", "created_at"),)


class ReasoningTrace(Base):
    """L5: Full reasoning trace for audit/debugging."""

    __tablename__ = "reasoning_traces"

    query_id = Column(String(36), primary_key=True)  # UUID
    query_text = Column(Text, nullable=False)
    trace_json = Column(JSON, nullable=False)  # Full tool call sequence
    answer = Column(Text)
    latency_ms = Column(Integer)
    iterations = Column(Integer)
    created_at = Column(DateTime, default=utc_now_naive)
    # No TTL - forever retention for compliance


class QueryLog(Base):
    """Query logging for analytics."""

    __tablename__ = "query_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(36), nullable=False)
    query_text = Column(Text, nullable=False)
    user_language = Column(String(5))
    status = Column(String(20), default="processing", nullable=False)
    error_message = Column(Text)
    cache_hit = Column(Boolean, default=False)
    latency_ms = Column(Integer)
    iterations = Column(Integer)
    confidence = Column(String(10))
    created_at = Column(DateTime, default=utc_now_naive)

    __table_args__ = (Index("ix_query_log_query_id", "query_id"),)


class UserFeedback(Base):
    """User feedback on answers."""

    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(36), nullable=False)
    rating = Column(String(10))  # thumbs_up, thumbs_down
    category = Column(String(50))  # wrong_answer, incomplete, bad_citation, other
    details = Column(Text)
    created_at = Column(DateTime, default=utc_now_naive)

    __table_args__ = (Index("ix_user_feedback_query_id", "query_id"),)


class Embedding(Base):
    """L3: Paragraph embeddings for fallback search (Phase 2)."""

    __tablename__ = "embeddings"

    para_id = Column(
        String(100), ForeignKey("paragraphs.para_id", ondelete="CASCADE"), primary_key=True
    )
    vector = Column(LargeBinary, nullable=False)  # Serialized numpy array
    model_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utc_now_naive)

    # Relationships
    paragraph = relationship("Paragraph", back_populates="embeddings")


class IngestionCheckpoint(Base):
    """Checkpoint for resumable ingestion."""

    __tablename__ = "ingestion_checkpoints"

    doc_id = Column(String(255), primary_key=True)
    stage = Column(String(50), nullable=False)  # parsing, structure, annotation, indexing
    stage_data = Column(JSON)  # Stage-specific state
    error_message = Column(Text)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
