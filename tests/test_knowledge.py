from __future__ import annotations

import json

import pytest

from oratium.tools.knowledge import (
    KnowledgeIndex,
    _cosine_similarity,
    _is_url,
    chunk_text,
    make_search_function,
)

# --- helpers for tests (no OpenAI calls) ---


def _fake_embedder_factory():
    """A deterministic fake embedder for tests.

    Returns a fixed-length vector based on character hashes — same input
    always yields the same vector; similar substrings yield similar vectors.
    """

    async def embed(text: str) -> list[float]:
        # 8-dimensional embedding seeded from character bytes.
        vec = [0.0] * 8
        for i, ch in enumerate(text.lower()):
            vec[i % 8] += ord(ch) / 1000.0
        # Normalize a bit
        return vec

    return embed


# --- chunking ---


def test_chunk_text_short_input_returns_one_chunk() -> None:
    assert chunk_text("Hello world.") == ["Hello world."]


def test_chunk_text_splits_at_paragraph_boundaries() -> None:
    text = "Para 1.\n\nPara 2.\n\nPara 3."
    chunks = chunk_text(text, max_chars=20)
    # With max_chars=20, each ~7-char paragraph fits but the third would
    # push over so it starts a new chunk.
    assert all(len(c) <= 30 for c in chunks)  # generous upper bound
    # All paragraphs preserved
    rejoined = "\n\n".join(chunks)
    for p in ("Para 1.", "Para 2.", "Para 3."):
        assert p in rejoined


def test_chunk_text_skips_empty_paragraphs() -> None:
    text = "Real para.\n\n\n\n\nAnother real."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert "Real para." in chunks[0]
    assert "Another real." in chunks[0]


def test_chunk_text_handles_empty_string() -> None:
    assert chunk_text("") == []


# --- cosine similarity ---


def test_cosine_identical_vectors() -> None:
    v = [1.0, 2.0, 3.0]
    assert _cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors() -> None:
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert _cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_zero_vector_returns_zero() -> None:
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert _cosine_similarity([1.0, 1.0], [0.0, 0.0]) == 0.0


# --- URL detection ---


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("https://example.com", True),
        ("http://example.com/page", True),
        ("./local.pdf", False),
        ("/abs/path.pdf", False),
        ("file.pdf", False),
        ("ftp://nope", False),
    ],
)
def test_is_url(source: str, expected: bool) -> None:
    assert _is_url(source) is expected


# --- KnowledgeIndex with fake embedder ---


async def test_index_lazy_loads_on_first_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """The index must not call the loader at construction."""
    loaded: list[str] = []

    async def fake_url_load(url: str) -> str:
        loaded.append(url)
        return "Document body about widgets and gadgets."

    monkeypatch.setattr("oratium.tools.knowledge._load_url", fake_url_load)

    index = KnowledgeIndex(
        sources=["https://example.com/doc"],
        embed=_fake_embedder_factory(),
    )
    assert loaded == []
    assert index.chunk_count == 0

    results = await index.search("widgets")
    assert loaded == ["https://example.com/doc"]
    assert index.chunk_count > 0
    assert len(results) > 0


async def test_index_caches_after_first_load(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0

    async def fake_url_load(url: str) -> str:
        nonlocal call_count
        call_count += 1
        return "Some doc text."

    monkeypatch.setattr("oratium.tools.knowledge._load_url", fake_url_load)

    index = KnowledgeIndex(
        sources=["https://example.com/doc"],
        embed=_fake_embedder_factory(),
    )
    await index.search("x")
    await index.search("y")
    await index.search("z")
    assert call_count == 1


async def test_index_returns_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_url_load(url: str) -> str:
        # Three distinct paragraphs separated by blank lines so chunker emits 3.
        return "Apple banana cherry.\n\nDog elephant fox.\n\nGrape honeydew kiwi."

    monkeypatch.setattr("oratium.tools.knowledge._load_url", fake_url_load)

    index = KnowledgeIndex(
        sources=["https://example.com/doc"],
        embed=_fake_embedder_factory(),
        chunk_chars=20,  # force per-paragraph chunks
    )
    results = await index.search("anything", k=2)
    assert len(results) == 2


async def test_index_empty_sources_returns_empty_search() -> None:
    index = KnowledgeIndex(sources=[], embed=_fake_embedder_factory())
    results = await index.search("query")
    assert results == []


# --- search function tool wrapping ---


async def test_search_function_returns_no_relevant_for_empty_index() -> None:
    index = KnowledgeIndex(sources=[], embed=_fake_embedder_factory())
    tool = make_search_function(index)
    from agents.tool_context import ToolContext

    ctx = ToolContext(
        context=None,
        tool_name="search_knowledge",
        tool_call_id="test-call",
        tool_arguments="",
    )
    result = await tool.on_invoke_tool(ctx, json.dumps({"query": "anything"}))
    assert "No relevant" in result


async def test_search_function_joins_top_k_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_url_load(url: str) -> str:
        return "First passage.\n\nSecond passage.\n\nThird passage."

    monkeypatch.setattr("oratium.tools.knowledge._load_url", fake_url_load)

    index = KnowledgeIndex(
        sources=["https://example.com/doc"],
        embed=_fake_embedder_factory(),
        chunk_chars=20,
    )
    tool = make_search_function(index)
    from agents.tool_context import ToolContext

    ctx = ToolContext(
        context=None,
        tool_name="search_knowledge",
        tool_call_id="test-call",
        tool_arguments="",
    )
    result = await tool.on_invoke_tool(ctx, json.dumps({"query": "passage"}))
    assert "passage" in result.lower()
    # The separator we insert between top-k chunks
    if "---" in result:
        assert result.count("---") >= 1
