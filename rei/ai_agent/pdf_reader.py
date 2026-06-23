"""Extract per-page text from planning PDFs."""
from __future__ import annotations

from pathlib import Path

from rei.common.logging import get_logger

log = get_logger(__name__)


def extract_pages(pdf_path: str | Path) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages.append((i, page.extract_text() or ""))
    except Exception:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        for i, page in enumerate(reader.pages, start=1):
            pages.append((i, page.extract_text() or ""))
    empty = sum(1 for _, t in pages if len(t.strip()) < 20)
    if empty:
        log.warning("%s: %d/%d pages have little/no text (consider OCR)", pdf_path, empty, len(pages))
    return pages
