"""Rebuild Qdrant collections from the DuckDB ledger alone."""

from __future__ import annotations

from nornikel_kg.services.runtime import get_retrieval_service


def main() -> None:
    service = get_retrieval_service()
    if not service.enabled:
        print("Retrieval index is disabled (EMBEDDING_BACKEND=off); nothing to do.")
        return
    total = service.reindex_all()
    print(f"Reindexed {total} units into Qdrant.")


if __name__ == "__main__":
    main()
