"""Batch-ingest a real document corpus directory into the ledger.

Runs inside the api container (no HTTP hop), file by file, with per-file
size caps and quarantine-over-crash semantics:

    docker compose -f docker-compose.server.yml stop api   # release the DB lock
    docker compose -f docker-compose.server.yml run --rm --no-deps -T api \
        python scripts/ingest_corpus.py --dir data/corpus --limit 60
    docker compose -f docker-compose.server.yml up -d

LOCK CONTRACT: the API process holds a persistent DuckDB write connection,
so this script and a running API are mutually exclusive — whichever opens
the file first wins and the other sees lock errors. Stop the api container
for the batch window (the script fails fast with a clear message otherwise).

Archives are expanded first: .zip, multipart .zip.001/.002 (reassembled by
byte concatenation), and .rar (via bsdtar when installed). Images (.gif/.jpg/
.png/.tif) are counted as no-OCR skips — never silently dropped.
"""

from __future__ import annotations

import argparse
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from nornikel_kg.services.archive_expansion import expand_archives

SUPPORTED = {
    ".pdf",
    ".docx",
    ".docm",
    ".doc",
    ".csv",
    ".md",
    ".markdown",
    ".txt",
    ".xlsx",
    ".xls",
    ".pptx",
    ".text",
}
IMAGE_EXTENSIONS = {".gif", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
ARCHIVE_EXTENSIONS = {".zip", ".rar"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="Corpus directory (recursed)")
    parser.add_argument("--limit", type=int, default=0, help="Max files to ingest (0 = all)")
    parser.add_argument("--max-mb", type=float, default=20.0, help="Per-file size cap")
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Concurrent ingest workers — overlaps LLM/embedding I/O across files "
        "(Docling parsing is serialized internally for thread-safety)",
    )
    args = parser.parse_args()

    from nornikel_kg.services.runtime import get_ingestion_service, get_ledger_repository

    try:
        get_ledger_repository().migrate()
    except Exception as error:
        raise SystemExit(
            f"Cannot open the ledger (is the api container holding the DuckDB "
            f"lock? stop it for the batch window): {error!r}"
        ) from error

    service = get_ingestion_service()
    service.synchronous_enrichment = True  # batch runs want completed statuses

    stats = {
        "completed": 0,
        "quarantined": 0,
        "failed": 0,
        "skipped": 0,
        "too_large": 0,
        "images_no_ocr": 0,
    }
    started = time.time()
    all_files = sorted(path for path in Path(args.dir).rglob("*") if path.is_file())

    with tempfile.TemporaryDirectory(prefix="corpus_archives_") as work_dir:
        extracted, archive_stats = expand_archives(all_files, Path(work_dir))
        if archive_stats:
            print(f"Archives: {dict(archive_stats)} -> {len(extracted)} extracted files")
        files = all_files + sorted(extracted)

        # Pre-filter (fast, sequential): images, archives/unsupported, oversized.
        to_ingest: list[Path] = []
        for path in files:
            if args.limit and len(to_ingest) >= args.limit:
                break
            suffix = path.suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                stats["images_no_ocr"] += 1
                continue
            if suffix in ARCHIVE_EXTENSIONS or suffix not in SUPPORTED:
                if suffix not in ARCHIVE_EXTENSIONS:
                    stats["skipped"] += 1
                continue
            size_mb = path.stat().st_size / 1024 / 1024
            if size_mb > args.max_mb:
                stats["too_large"] += 1
                print(f"TOO_LARGE ({size_mb:.0f}MB) {path.name[:70]}")
                continue
            to_ingest.append(path)

        total = len(to_ingest)
        stats_lock = threading.Lock()
        done = [0]

        def _ingest_one(path: Path) -> None:
            file_started = time.time()
            try:
                response = service.ingest_upload(filename=path.name, content=path.read_bytes())
                status = response.source.status
                key = status if status in stats else "completed"
                with stats_lock:
                    stats[key] = stats.get(key, 0) + 1
                    done[0] += 1
                    marker = done[0]
                print(
                    f"[{marker:4d}/{total}] {status.upper():<11} "
                    f"{time.time() - file_started:5.1f}s {response.evidence_count:4d} spans  "
                    f"{path.name[:60]}"
                )
            except Exception as error:  # a single bad file must never stop the batch
                with stats_lock:
                    stats["failed"] += 1
                    done[0] += 1
                print(f"FAILED       {path.name[:60]}: {error!r}")

        if args.workers > 1:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                list(pool.map(_ingest_one, to_ingest))
        else:
            for path in to_ingest:
                _ingest_one(path)
        ingested = total
    elapsed = time.time() - started
    print(
        f"\nDone in {elapsed:.0f}s: {stats} "
        f"({ingested} ingested of {len(all_files)} files seen)"
    )


if __name__ == "__main__":
    main()
