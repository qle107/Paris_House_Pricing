"""Structured extraction from planning document chunks."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from rei.ai_agent import prompts
from rei.ai_agent.llm import chat
from rei.ai_agent.rag import retrieve
from rei.common.db import connection
from rei.common.logging import get_logger
from config.settings import settings

log = get_logger(__name__)

FACT_TYPES = ["density_increase", "rezoning", "housing_target", "transport", "redevelopment"]


def assemble_context(commune: str, k_each: int = 4, max_chars: int = 9000) -> str:
    """Retrieve the most relevant chunks across all signal queries, with page refs."""
    seen: set[int] = set()
    blocks: list[str] = []
    for q in prompts.RETRIEVAL_QUERIES:
        for r in retrieve(q, commune=commune, k=k_each):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            blocks.append(f"[doc {r['document_id']} p.{r['page_from']}] {r['content']}")
    context = "\n\n".join(blocks)
    return context[:max_chars]


def build_messages(commune: str, context: str) -> list[dict]:
    user = prompts.EXTRACTION_TEMPLATE.format(commune=commune, context=context)
    return [{"role": "system", "content": prompts.SYSTEM},
            {"role": "user", "content": user}]


def export_prompt(commune: str, out_dir: str | Path = "prompts_out") -> Path:
    """Write a single copy-pasteable prompt file for `commune`."""
    context = assemble_context(commune)
    if not context.strip():
        log.warning("No embedded context for %s - crawl + embed documents first", commune)
    msgs = build_messages(commune, context)
    text_block = f"### SYSTEM\n{msgs[0]['content']}\n\n### TASK\n{msgs[1]['content']}\n"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"prompt_{commune}.txt"
    path.write_text(text_block, encoding="utf-8")
    log.info("Wrote copy/paste prompt -> %s", path)
    return path


def ingest_response(commune: str, json_text: str, document_id: int | None = None) -> int:
    """Parse a pasted JSON answer and store every fact in docs.extraction."""
    data = _loads_lenient(json_text)
    n = 0
    with connection() as conn:
        for ftype in FACT_TYPES:
            for item in data.get(ftype, []) or []:
                conn.execute(
                    text(
                        "INSERT INTO docs.extraction (document_id, code_commune, fact_type, payload, confidence) "
                        "VALUES (:d, :c, :t, :p, :conf)"
                    ),
                    {"d": document_id, "c": commune, "t": ftype,
                     "p": json.dumps(item, ensure_ascii=False),
                     "conf": float(item.get("confidence", 0.5)) if isinstance(item, dict) else 0.5},
                )
                n += 1
    log.info("Stored %d extracted facts for %s", n, commune)
    return n


def extract_auto(commune: str, document_id: int | None = None) -> int:
    """Run extraction via the configured provider (ollama/openai) end-to-end."""
    if settings.llm_provider == "manual":
        raise RuntimeError("LLM_PROVIDER=manual; use export_prompt + ingest_response")
    context = assemble_context(commune)
    raw = chat(build_messages(commune, context))
    return ingest_response(commune, raw, document_id)


def _loads_lenient(s: str) -> dict:
    """Parse JSON even if wrapped in markdown fences or trailing prose."""
    s = s.strip()
    if "```" in s:
        s = s.split("```")[1].lstrip("json").strip() if s.count("```") >= 2 else s
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1:
        s = s[start:end + 1]
    return json.loads(s)
