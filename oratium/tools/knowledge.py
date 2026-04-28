"""Knowledge sources — RAG over PDFs and web URLs.

PDFs (via :mod:`pypdf`) and web URLs (via :mod:`httpx` + :mod:`bs4`) are
chunked at paragraph boundaries, embedded with OpenAI's
``text-embedding-3-small`` (or any compatible embedder), and held in an
in-memory ``KnowledgeIndex``. The index exposes a single ``search_knowledge``
function tool to the agent. Loading is lazy: the first ``search`` call
triggers ingestion.

Adopters who need Pinecone / Weaviate / FAISS swap the index implementation
behind the same interface (post-v0).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import pypdf
from agents import function_tool
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EmbedFn = Callable[[str], Awaitable[list[float]]]

DEFAULT_CHUNK_CHARS = 1000
DEFAULT_TOP_K = 3
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def _is_url(s: str) -> bool:
    return urlparse(s).scheme in ("http", "https")


def _load_pdf(path: Path) -> str:
    reader = pypdf.PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


async def _load_url(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return str(soup.get_text(separator="\n\n", strip=True))


def chunk_text(text: str, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    """Split text into paragraph-aligned chunks of roughly ``max_chars`` each."""
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if current and current_size + len(paragraph) > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_size = 0
        current.append(paragraph)
        current_size += len(paragraph) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def make_openai_embedder(api_key: str, model: str = DEFAULT_EMBEDDING_MODEL) -> EmbedFn:
    """Return an embedder callable that uses the OpenAI embeddings API.

    Constructed lazily inside the function so the import only fires when
    a knowledge source is actually configured.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)

    async def embed(text: str) -> list[float]:
        resp = await client.embeddings.create(model=model, input=[text])
        return list(resp.data[0].embedding)

    return embed


class KnowledgeIndex:
    """In-memory vector index over text chunks, lazy on first search.

    Sources are loaded and embedded the first time :meth:`search` is called,
    not at construction. Subsequent searches reuse the cached chunks.
    """

    def __init__(
        self,
        sources: list[str],
        *,
        embed: EmbedFn,
        chunk_chars: int = DEFAULT_CHUNK_CHARS,
    ) -> None:
        self._sources = list(sources)
        self._embed = embed
        self._chunk_chars = chunk_chars
        self._chunks: list[tuple[str, list[float]]] = []
        self._loaded = False

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    async def _ingest(self) -> None:
        if self._loaded:
            return
        for source in self._sources:
            if _is_url(source):
                logger.info("Ingesting knowledge from URL: %s", source)
                text = await _load_url(source)
            else:
                logger.info("Ingesting knowledge from file: %s", source)
                text = _load_pdf(Path(source))
            chunks = chunk_text(text, max_chars=self._chunk_chars)
            for chunk in chunks:
                embedding = await self._embed(chunk)
                self._chunks.append((chunk, embedding))
        logger.info(
            "Knowledge index ready: %d chunks across %d sources",
            len(self._chunks),
            len(self._sources),
        )
        self._loaded = True

    async def search(self, query: str, k: int = DEFAULT_TOP_K) -> list[str]:
        await self._ingest()
        if not self._chunks:
            return []
        query_emb = await self._embed(query)
        scored = [(text, _cosine_similarity(query_emb, emb)) for text, emb in self._chunks]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [text for text, _ in scored[:k]]


def make_search_function(index: KnowledgeIndex) -> Any:
    """Build a ``function_tool`` that searches the knowledge index."""

    async def search_knowledge(query: str) -> str:
        """Search the knowledge base for information relevant to the query.

        Use this whenever the caller asks about content that may live in
        the documents you've been given. Returns the most relevant
        passages; if the answer needs synthesis across passages, do that
        in your reply.
        """
        results = await index.search(query, k=DEFAULT_TOP_K)
        if not results:
            return "No relevant information found in the knowledge base."
        return "\n\n---\n\n".join(results)

    return function_tool(search_knowledge)
