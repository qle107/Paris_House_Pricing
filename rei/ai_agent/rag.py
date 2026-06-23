"""Chunk, embed, and retrieve document passages (pgvector)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from rei.ai_agent.llm import embed
from rei.ai_agent.pdf_reader import extract_pages
from rei.common.db import connection, get_engine
from rei.common.io import cache_path
from rei.common.logging import get_logger

log = get_logger(__name__)


def chunk_pages(pages: list[tuple[int, str]], words_per_chunk: int = 350, overlap: int = 60):
    """Yield (page_from, page_to, text). Word-based ~= 500 tokens for FR text."""
    for page_no, txt in pages:
        words = (txt or "").split()
        if not words:
            continue
        i = 0
        while i < len(words):
            window = words[i:i + words_per_chunk]
            yield (page_no, page_no, " ".join(window))
            i += words_per_chunk - overlap


def embed_document(doc_id: int) -> int:
    pdf_path = cache_path("documents", f"{doc_id}.pdf")
    if not Path(pdf_path).exists():
        log.warning("PDF missing for doc %s", doc_id)
        return 0
    chunks = list(chunk_pages(extract_pages(pdf_path)))
    if not chunks:
        return 0
    vectors = embed([c[2] for c in chunks], is_query=False)
    with connection() as conn:
        for idx, ((pf, pt, content), vec) in enumerate(zip(chunks, vectors)):
            conn.execute(
                text(
                    "INSERT INTO docs.chunk (document_id, chunk_index, page_from, page_to, content, token_count, embedding) "
                    "VALUES (:d, :i, :pf, :pt, :c, :tk, (:emb)::vector) "
                    "ON CONFLICT (document_id, chunk_index) DO UPDATE SET content=EXCLUDED.content, embedding=EXCLUDED.embedding"
                ),
                {"d": doc_id, "i": idx, "pf": pf, "pt": pt, "c": content,
                 "tk": len(content.split()), "emb": _vec_literal(vec)},
            )
        conn.execute(text("UPDATE docs.document SET status='embedded' WHERE id=:i"), {"i": doc_id})
    log.info("Embedded %d chunks for doc %s", len(chunks), doc_id)
    return len(chunks)


def retrieve(query: str, commune: str | None = None, k: int = 8) -> list[dict]:
    qvec = embed([query], is_query=True)[0]
    sql = (
        "SELECT c.id, c.document_id, c.page_from, c.content, "
        "       1 - (c.embedding <=> (:q)::vector) AS similarity "
        "FROM docs.chunk c JOIN docs.document d ON d.id = c.document_id "
        + ("WHERE d.code_commune = :commune " if commune else "")
        + "ORDER BY c.embedding <=> (:q)::vector LIMIT :k"
    )
    params = {"q": _vec_literal(qvec), "k": k}
    if commune:
        params["commune"] = commune
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
