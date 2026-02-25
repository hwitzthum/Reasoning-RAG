"""Logging configuration for Reasoning-RAG.

This module provides centralized logging configuration with support for both
development (readable) and production (JSON) formats.
"""

import logging
import sys
from typing import Any
import json
from datetime import UTC, datetime

from app.config import settings


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production environments.

    Formats log records as single-line JSON objects for easy parsing
    by log aggregation tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            str: JSON-formatted log line
        """
        timestamp_utc = datetime.fromtimestamp(record.created, UTC)
        log_data: dict[str, Any] = {
            "timestamp": timestamp_utc.isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "query_id"):
            log_data["query_id"] = record.query_id
        if hasattr(record, "doc_id"):
            log_data["doc_id"] = record.doc_id

        return json.dumps(log_data)


class ReadableFormatter(logging.Formatter):
    """Human-readable log formatter for development.

    Provides colored output and readable multi-line format for
    better development experience.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record in readable style.

        Args:
            record: Log record to format

        Returns:
            str: Formatted log line with colors
        """
        # Get color for level
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created, UTC).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Base format
        formatted = (
            f"{color}{record.levelname:8}{reset} "
            f"{timestamp} "
            f"{record.module}:{record.funcName}:{record.lineno} - "
            f"{record.getMessage()}"
        )

        # Add exception if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def configure_logging() -> None:
    """Configure application-wide logging.

    Sets up logging based on settings.log_level with appropriate
    formatters for production vs development.
    """
    # Get log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers = []

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Choose formatter based on environment
    if settings.log_level == "DEBUG":
        # Development: readable format
        formatter = ReadableFormatter()
    else:
        # Production: JSON format
        formatter = JSONFormatter()

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set library log levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    # Log startup message
    root_logger.info(
        f"Logging configured: level={settings.log_level.upper()}, "
        f"format={'readable' if settings.log_level == 'DEBUG' else 'JSON'}"
    )


def get_logger(name: str) -> logging.Logger:
    """Get logger for a specific module.

    This is a factory function for creating module-specific loggers
    that inherit the application-wide configuration.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return logging.getLogger(name)


# Request logging middleware would be added to main.py
# This is a placeholder for the middleware implementation
