"""CLI for the AI research agent (crawl, embed, extract, alerts)."""
from __future__ import annotations

import argparse
from pathlib import Path

from rei.ai_agent import alerts, crawler, extractors, rag
from rei.common.db import get_engine
from sqlalchemy import text


def _pending_doc_ids(status: str, limit: int = 100) -> list[int]:
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("SELECT id FROM docs.document WHERE status=:s LIMIT :n"),
            {"s": status, "n": limit},
        ).fetchall()
    return [r[0] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(prog="rei.ai_agent.run")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("crawl")
    sub.add_parser("embed")

    p = sub.add_parser("export-prompt"); p.add_argument("--commune", required=True); p.add_argument("--out", default="prompts_out")
    p = sub.add_parser("ingest"); p.add_argument("--commune", required=True); p.add_argument("--file", required=True)
    p = sub.add_parser("auto"); p.add_argument("--commune", required=True)
    p = sub.add_parser("alerts"); p.add_argument("--communes", required=True)

    args = ap.parse_args()
    if args.cmd == "crawl":
        print("fetched:", crawler.download_pending())
    elif args.cmd == "embed":
        ids = _pending_doc_ids("fetched")
        print("embedded chunks:", sum(rag.embed_document(i) for i in ids))
    elif args.cmd == "export-prompt":
        print("prompt written to:", extractors.export_prompt(args.commune, args.out))
    elif args.cmd == "ingest":
        txt = Path(args.file).read_text(encoding="utf-8")
        print("facts stored:", extractors.ingest_response(args.commune, txt))
    elif args.cmd == "auto":
        print("facts stored:", extractors.extract_auto(args.commune))
    elif args.cmd == "alerts":
        print(alerts.generate_alerts(args.communes.split(",")).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
