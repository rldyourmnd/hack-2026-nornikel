from __future__ import annotations

from nornikel_kg.adapters.embeddings.fake import FakeEmbeddingBackend
from nornikel_kg.adapters.embeddings.local import LocalEmbeddingBackend
from nornikel_kg.adapters.embeddings.yandex import YandexEmbeddingBackend

__all__ = ["FakeEmbeddingBackend", "LocalEmbeddingBackend", "YandexEmbeddingBackend"]
