from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from nornikel_kg.adapters.embeddings.openai_compat import OpenAIEmbeddingBackend


def test_openai_embedding_batches_and_preserves_order(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OpenAIEmbeddingBackend(api_base="https://x/v1", api_key="k", model="m")
    seen: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], headers: dict[str, str], timeout: float) -> Any:
        seen["url"] = url
        seen["auth"] = headers["Authorization"]
        n = len(json["input"])
        data = [{"index": i, "embedding": [float(i)]} for i in range(n)]
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"data": list(reversed(data))},  # out of order on purpose
            raise_for_status=lambda: None,
            text="",
        )

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    out = backend.embed_dense(["a", "b", "c"])
    assert out == [[0.0], [1.0], [2.0]]  # re-sorted by index
    assert seen["url"] == "https://x/v1/embeddings"
    assert seen["auth"] == "Bearer k"


def test_openai_embedding_requires_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_BASE", raising=False)
    monkeypatch.delenv("DATAEYES_API_BASE", raising=False)
    with pytest.raises(ValueError):
        OpenAIEmbeddingBackend(api_key="k", model="m")


def test_openai_embedding_rejects_short_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 with fewer/misaligned items must raise (retried, then loud) — never
    silently return a short vector list that unindexes or misaligns a source."""
    backend = OpenAIEmbeddingBackend(api_base="https://x/v1", api_key="k", model="m")
    import httpx

    def short_post(url: str, json: Any, headers: Any, timeout: float) -> Any:
        # two inputs requested, only one vector returned
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"data": [{"index": 0, "embedding": [1.0]}]},
            raise_for_status=lambda: None,
            text="",
        )

    monkeypatch.setattr(httpx, "post", short_post)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    with pytest.raises(RuntimeError):
        backend.embed_dense(["a", "b"])
