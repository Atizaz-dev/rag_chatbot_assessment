"""Lightweight local vector store built on OpenAI embeddings.

This module chunks uploaded PDF text, embeds the chunks, persists them to disk,
and exposes helpers to retrieve the most relevant chunks for a query.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import pickle
from dataclasses import dataclass
from typing import Sequence

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)


# --- Configuration ----------------------------------------------------------------

VECTOR_STORE_DIR = os.getenv("VECTOR_STORE_DIR", "pdf_embeddings")
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
DEFAULT_CHUNK_SIZE = int(os.getenv("EMBED_CHUNK_SIZE", "1200"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("EMBED_CHUNK_OVERLAP", "200"))

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_client: OpenAI | None = None
if _OPENAI_API_KEY:
    try:
        _client = OpenAI(api_key=_OPENAI_API_KEY)
    except Exception as exc:  # pragma: no cover - defensive init
        logger.exception("Failed to initialise OpenAI client: %s", exc)
        _client = None
else:
    logger.warning("OPENAI_API_KEY missing; vector embeddings disabled.")


# --- Internal helpers --------------------------------------------------------------


def _embedding_path(pdf_id: str) -> str:
    return os.path.join(VECTOR_STORE_DIR, f"{pdf_id}.pkl")


def _chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Simple character-based chunker with overlap."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    step = chunk_size - overlap

    while start < length:
        end = min(start + chunk_size, length)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks


def _embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if not _client:
        raise RuntimeError("OPENAI_API_KEY is required to generate embeddings")

    embeddings: list[list[float]] = []
    batch_size = 16
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = _client.embeddings.create(model=EMBED_MODEL, input=list(batch))
        embeddings.extend([item.embedding for item in response.data])
    return embeddings


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(x * x for x in vec_a))
    norm_b = math.sqrt(sum(y * y for y in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class ChunkEmbedding:
    chunk: str
    embedding: list[float]
    pdf_id: str
    idx: int


# --- Public API --------------------------------------------------------------------


def store_pdf_embeddings(pdf_id: str, text: str) -> None:
    """Chunk text, generate embeddings, and persist them to disk."""

    if not text.strip():
        logger.info("Skipping embedding for pdf %s (empty text)", pdf_id)
        return

    if not _client:
        logger.warning("Embeddings disabled (missing API key); skipping store for %s", pdf_id)
        return

    chunks = _chunk_text(text)
    if not chunks:
        logger.info("No chunks generated for pdf %s", pdf_id)
        return

    logger.info("Embedding %d chunks for pdf %s", len(chunks), pdf_id)
    embeddings = _embed_texts(chunks)

    payload = {
        "chunks": chunks,
        "embeddings": embeddings,
    }

    path = _embedding_path(pdf_id)
    with open(path, "wb") as fh:
        pickle.dump(payload, fh)
    logger.info("Stored embeddings for pdf %s at %s", pdf_id, path)


def delete_pdf_embeddings(pdf_id: str) -> None:
    path = _embedding_path(pdf_id)
    if os.path.exists(path):
        os.remove(path)


def cleanup_embeddings(keep_pdf_id: str) -> None:
    """Remove stale embedding files, keeping only the specified pdf id."""

    try:
        filenames = os.listdir(VECTOR_STORE_DIR)
    except FileNotFoundError:  # pragma: no cover - directory missing
        return

    keep_filename = f"{keep_pdf_id}.pkl"
    for name in filenames:
        if not name.endswith(".pkl"):
            continue
        if name == keep_filename:
            continue
        path = os.path.join(VECTOR_STORE_DIR, name)
        try:
            os.remove(path)
            logger.info("Removed stale embedding file: %s", path)
        except OSError:
            logger.exception("Failed to delete embedding file: %s", path)


def load_pdf_embeddings(pdf_id: str) -> list[ChunkEmbedding]:
    path = _embedding_path(pdf_id)
    if not os.path.exists(path):
        return []

    with open(path, "rb") as fh:
        data = pickle.load(fh)

    chunks: list[str] = data.get("chunks", [])
    embeddings: list[list[float]] = data.get("embeddings", [])
    results: list[ChunkEmbedding] = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        results.append(ChunkEmbedding(chunk=chunk, embedding=emb, pdf_id=pdf_id, idx=idx))
    return results


def retrieve_relevant_chunks(
    pdf_ids: Sequence[str],
    query: str,
    top_k: int = 5,
) -> list[str]:
    """Return the top-k chunk texts most similar to the query."""

    if not pdf_ids or not query.strip():
        return []

    if not _client:
        logger.warning("Embeddings disabled; returning no chunks")
        return []

    docs: list[ChunkEmbedding] = []
    for pdf_id in pdf_ids:
        docs.extend(load_pdf_embeddings(pdf_id))

    if not docs:
        return []

    query_embedding = _embed_texts([query])[0]

    scored = [
        (doc, _cosine_similarity(query_embedding, doc.embedding))
        for doc in docs
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    top_chunks = [doc.chunk for doc, _score in scored[:top_k]]
    return top_chunks


async def async_store_pdf_embeddings(pdf_id: str, text: str) -> None:
    """Async wrapper to avoid blocking the event loop."""

    await asyncio.to_thread(store_pdf_embeddings, pdf_id, text)

