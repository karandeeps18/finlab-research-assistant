"""Structured logging setup.

We use structlog:
  - structured (JSON, not free text) — so log aggregators can parse it
  - context-aware (request_id, ticker, etc.) — so we can trace a single
    request across many log lines
  - level-appropriate (debug/info/warning/error)

In dev we render to pretty console output. In prod (via env var) we'd
render to JSON. We'll keep it console-pretty for the whole project.
"""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging.

    Call this once at app startup.
    """
    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            min_level=numeric_level
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger for a module. Use module __name__."""
    return structlog.get_logger(name)