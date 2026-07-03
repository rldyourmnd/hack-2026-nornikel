"""Pre-pull heavyweight model weights (Docling, GLiNER, embeddings) into HF_HOME.

Run on the server after deploy so the first user request is fast:
    docker compose -f docker-compose.server.yml exec api python scripts/warmup.py
"""

from __future__ import annotations

import os


def warm_docling() -> None:
    from docling.utils.model_downloader import download_models

    print("Warming Docling models...")
    download_models(with_easyocr=False)
    print("Docling models ready.")


def warm_gliner() -> None:
    if os.getenv("GLINER_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        print("GLiNER disabled; skipping.")
        return
    from nornikel_kg.adapters.gliner_ner.extractor import _load_model

    print("Warming GLiNER...")
    _load_model()
    print("GLiNER ready.")


def warm_embeddings() -> None:
    if os.getenv("EMBEDDING_BACKEND", "off").lower() != "local":
        print("Local embeddings disabled; skipping.")
        return
    from nornikel_kg.adapters.embeddings.local import _dense_model, _sparse_model

    print("Warming embedding models...")
    _dense_model()
    _sparse_model()
    print("Embedding models ready.")


def main() -> None:
    for step in (warm_docling, warm_gliner, warm_embeddings):
        try:
            step()
        except Exception as error:  # warmup is best-effort by design
            print(f"WARN: {step.__name__} failed: {error}")


if __name__ == "__main__":
    main()
