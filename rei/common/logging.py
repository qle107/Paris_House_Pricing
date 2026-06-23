"""Structured logging used across the platform."""
from __future__ import annotations

import logging
import sys

from config.settings import settings

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
        )
        root = logging.getLogger()
        root.handlers[:] = [handler]
        root.setLevel(settings.log_level.upper())
        _CONFIGURED = True
    return logging.getLogger(name)
