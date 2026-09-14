"""structlog: у dev — кольорова консоль, у prod — JSON у stdout (ADR-0002).

ADR-0009: payload подій у prod не логувати цілком — це правило для коду,
що пише в лог, не для конфігу.
"""

import logging
from typing import Literal

import structlog


def configure_logging(app_env: Literal["dev", "prod"]) -> None:
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if app_env == "prod"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
