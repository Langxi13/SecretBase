from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def close_logging_before_temp_cleanup() -> Iterator[None]:
    """Release file handlers before Windows removes a temporary runtime directory."""
    try:
        yield
    finally:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            try:
                handler.flush()
            finally:
                handler.close()
                root_logger.removeHandler(handler)
        if hasattr(root_logger, "_secretbase_logging_configured"):
            delattr(root_logger, "_secretbase_logging_configured")
