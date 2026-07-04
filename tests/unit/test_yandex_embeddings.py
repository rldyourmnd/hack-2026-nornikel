from __future__ import annotations

import pytest

from nornikel_kg.adapters.embeddings.yandex import YandexEmbeddingBackend


@pytest.fixture()
def backend(monkeypatch: pytest.MonkeyPatch) -> YandexEmbeddingBackend:
    monkeypatch.setenv("YANDEX_API_KEY", "test-key")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "test-folder")
    return YandexEmbeddingBackend()


def test_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)
    monkeypatch.delenv("YANDEX_FOLDER_ID", raising=False)
    with pytest.raises(ValueError):
        YandexEmbeddingBackend()


def test_doc_and_query_models_are_split(backend: YandexEmbeddingBackend) -> None:
    calls: list[tuple[str, str]] = []

    def fake_embed_one(text: str, model_uri: str) -> list[float]:
        calls.append((text, model_uri))
        return [0.1, 0.2]

    backend._embed_one = fake_embed_one  # type: ignore[method-assign]
    backend.embed_dense(["документ"])
    backend.embed_dense_query(["запрос"])
    assert calls[0][1] == backend.doc_model_uri
    assert calls[1][1] == backend.query_model_uri
    assert backend.doc_model_uri == "emb://test-folder/text-embeddings-v2-doc"
    assert backend.query_model_uri == "emb://test-folder/text-embeddings-v2-query"


def test_embedding_payload_uses_configured_dimension(
    backend: YandexEmbeddingBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"embedding": ["0.1", "0.2"]}

    def fake_post(url: str, **kwargs: object) -> Response:
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    vector = backend._embed_one("текст", backend.doc_model_uri)

    assert vector == [0.1, 0.2]
    assert captured["json"] == {
        "modelUri": "emb://test-folder/text-embeddings-v2-doc",
        "text": "текст",
        "dim": "768",
    }


def test_embed_many_preserves_order(backend: YandexEmbeddingBackend) -> None:
    backend._embed_one = (  # type: ignore[method-assign]
        lambda text, model_uri: [float(len(text))]
    )
    vectors = backend.embed_dense(["a", "bbb", "cc"])
    assert vectors == [[1.0], [3.0], [2.0]]


def test_sparse_stays_local_flat_query_weights(backend: YandexEmbeddingBackend) -> None:
    pytest.importorskip("fastembed")
    [query] = backend.embed_sparse_query(["шлак штейн"])
    assert all(value == 1.0 for value in query.values)


def test_query_embedding_cache_hits(backend: YandexEmbeddingBackend) -> None:
    calls: list[str] = []

    def fake_embed_many(texts: list[str], model_uri: str) -> list[list[float]]:
        calls.extend(texts)
        return [[1.0] for _ in texts]

    backend._embed_many = fake_embed_many  # type: ignore[method-assign]
    backend._query_cache.clear()
    backend.embed_dense_query(["повторный вопрос"])
    backend.embed_dense_query(["повторный вопрос"])
    assert calls == ["повторный вопрос"]  # second call served from cache
