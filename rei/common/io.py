"""Filesystem / download helpers with content-hash change detection."""
from __future__ import annotations

import gzip
import hashlib
import shutil
from pathlib import Path

from config.settings import settings


def cache_path(source_id: str, filename: str) -> Path:
    p = settings.raw_dir / source_id
    p.mkdir(parents=True, exist_ok=True)
    return p / filename


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def gunzip(src: Path, dest: Path | None = None) -> Path:
    dest = dest or src.with_suffix("")
    with gzip.open(src, "rb") as fi, open(dest, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    return dest


def changed_since(path: Path, known_hash: str | None) -> bool:
    """True if the file content differs from a previously stored hash.

    Used so a daily DAG can skip downstream work when an upstream file is byte
    identical to the last run (cheap, network-free idempotency for bulk files).
    """
    if not path.exists():
        return True
    return sha256(path) != known_hash
