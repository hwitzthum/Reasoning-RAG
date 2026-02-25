"""Custom exceptions for Reasoning-RAG API.

This module defines domain-specific exceptions and their HTTP mappings
for consistent error handling across the application.
"""


class IngestionError(Exception):
    """Raised when document ingestion fails.

    This includes parsing errors, structure analysis failures, or
    annotation problems during the ingestion pipeline.
    """

    def __init__(self, message: str, doc_id: str | None = None):
        self.message = message
        self.doc_id = doc_id
        super().__init__(message)


class QueryTimeoutError(Exception):
    """Raised when a query exceeds the configured timeout.

    Prevents runaway queries from consuming excessive resources.
    """

    def __init__(self, elapsed_seconds: float, query_id: str | None = None):
        self.elapsed_seconds = elapsed_seconds
        self.query_id = query_id
        super().__init__(
            f"Query execution timed out after {elapsed_seconds:.1f} seconds"
        )


class DocumentNotFoundError(Exception):
    """Raised when a requested document does not exist.

    This is raised during document retrieval, deletion, or when
    querying with a doc_id scope that doesn't exist.
    """

    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        super().__init__(f"Document not found: {doc_id}")


class ValidationError(Exception):
    """Raised when request validation fails.

    This includes invalid query parameters, malformed requests,
    or business logic validation failures.
    """

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)
