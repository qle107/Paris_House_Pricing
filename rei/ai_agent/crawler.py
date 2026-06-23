"""Crawl planning sites and download documents into docs.document."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from rei.common.db import connection, get_engine
from rei.common.http import HttpClient
from rei.common.io import cache_path, sha256
from rei.common.logging import get_logger

log = get_logger(__name__)


def fetch_rendered_html(url: str) -> str:
    """Render a JS-heavy page with Playwright (sync API)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="rei-platform/0.1 (+research)")
        page.goto(url, wait_until="networkidle", timeout=60_000)
        html = page.content()
        browser.close()
    return html


def download_pending(limit: int = 50) -> int:
    """Download documents in status 'discovered', store + hash, mark 'fetched'."""
    eng = get_engine()
    rows = eng.connect().execute(
        text("SELECT id, source_url, code_commune FROM docs.document "
             "WHERE status = 'discovered' LIMIT :n"),
        {"n": limit},
    ).fetchall()
    http = HttpClient(rps=1.0)
    n = 0
    for doc_id, url, commune in rows:
        try:
            dest: Path = cache_path("documents", f"{doc_id}.pdf")
            http.stream_to_file(url, dest)
            digest = sha256(dest)
            with connection() as conn:
                conn.execute(
                    text("UPDATE docs.document SET status='fetched', fetched_at=now(), sha256=:h WHERE id=:i"),
                    {"h": digest, "i": doc_id},
                )
            n += 1
            log.info("Fetched doc %s (%s)", doc_id, commune)
        except Exception as exc:  # noqa: BLE001
            with connection() as conn:
                conn.execute(text("UPDATE docs.document SET status='error' WHERE id=:i"), {"i": doc_id})
            log.warning("Failed doc %s: %s", doc_id, exc)
    return n
