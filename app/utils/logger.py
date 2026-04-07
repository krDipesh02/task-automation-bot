import logging
import os
from typing import Optional


DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_CONFIGURED = False


def configure_logging(level: Optional[str] = None) -> None:
    global _CONFIGURED

    if _CONFIGURED:
        return

    logging.basicConfig(
        level=getattr(logging, (level or DEFAULT_LOG_LEVEL).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
