"""Map source_id to a Collector instance."""
from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path

import yaml

from rei.ingestion.base import Collector

SOURCES_YAML = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"


@lru_cache
def load_registry() -> dict:
    with open(SOURCES_YAML, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]


def get_collector(source_id: str) -> Collector:
    spec = load_registry()[source_id]
    module_path, cls_name = spec["collector"].rsplit(".", 1)
    cls = getattr(importlib.import_module(module_path), cls_name)
    return cls()


def runnable_sources() -> list[str]:
    return [sid for sid, s in load_registry().items() if s.get("tier") == "runnable"]


def all_sources() -> list[str]:
    return list(load_registry().keys())
