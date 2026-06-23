"""Chat and embedding clients (Ollama/sentence-transformers by default)."""
from __future__ import annotations

from functools import lru_cache

from config.settings import settings
from rei.common.logging import get_logger

log = get_logger(__name__)


def chat(messages: list[dict], temperature: float = 0.0) -> str:
    if settings.llm_provider == "openai":
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=settings.openai_chat_model, messages=messages, temperature=temperature,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content
    # default: Ollama
    import ollama
    client = ollama.Client(host=settings.ollama_base_url)
    resp = client.chat(
        model=settings.ollama_chat_model, messages=messages,
        options={"temperature": temperature}, format="json",
    )
    return resp["message"]["content"]


@lru_cache
def _st_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embed_model)


def embed(texts: list[str], is_query: bool = False) -> list[list[float]]:
    if settings.embed_backend == "openai":
        from openai import OpenAI
        client = OpenAI()
        out = client.embeddings.create(model=settings.openai_embed_model, input=texts)
        return [d.embedding for d in out.data]
    # e5 models expect query:/passage: prefixes
    prefix = "query: " if is_query else "passage: "
    model = _st_model()
    vecs = model.encode([prefix + t for t in texts], normalize_embeddings=True)
    return vecs.tolist()
