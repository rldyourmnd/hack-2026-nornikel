from __future__ import annotations

import contextlib
import os
import re
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl

from nornikel_kg.adapters.duckdb.repositories import SourceIngestError
from nornikel_kg.domain.models import EvidenceSpan, SourceIngestResponse, SourceSummary
from nornikel_kg.ports.parser import ParserError
from nornikel_kg.services.archive_expansion import expand_archives
from nornikel_kg.services.retrieval_service import EVIDENCE_COLLECTION
from nornikel_kg.services.runtime import (
    get_ingestion_service,
    get_ledger_repository,
    get_retrieval_service,
)

router = APIRouter(prefix="/sources", tags=["sources"])

_MAX_UPLOAD_FILENAME_LENGTH = 160


def _max_upload_bytes() -> int:
    raw_value = os.getenv("MAX_SOURCE_UPLOAD_BYTES", "5242880")
    try:
        value = int(raw_value)
    except ValueError:
        return 5 * 1024 * 1024
    return max(1, value)


def _validated_upload_filename(filename: str | None) -> str:
    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )
    normalized = filename.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )
    if len(normalized) > _MAX_UPLOAD_FILENAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Uploaded filename is too long. "
                f"Maximum length is {_MAX_UPLOAD_FILENAME_LENGTH}."
            ),
        )
    if "/" in normalized or "\\" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded filename must not contain path separators.",
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded filename contains unsupported control characters.",
        )
    return normalized


@router.get("")
def list_sources() -> dict[str, list[SourceSummary]]:
    return {"sources": get_ledger_repository().list_sources()}


@router.get("/{source_id}/evidence")
def list_source_evidence(source_id: str) -> dict[str, list[EvidenceSpan]]:
    repository = get_ledger_repository()
    if repository.get_source(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return {"evidence": repository.list_evidence_spans(source_id)}


@router.delete("/{source_id}")
def delete_source(source_id: str) -> dict[str, object]:
    repository = get_ledger_repository()
    if not repository.delete_source(source_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    # Vector index cleanup is best-effort: DuckDB rejoin already guards reads.
    retrieval = get_retrieval_service()
    if retrieval.index is not None:
        with contextlib.suppress(Exception):
            retrieval.index.delete_source_units(EVIDENCE_COLLECTION, source_id)
    return {"source_id": source_id, "deleted": True}


_ALLOWED_UPLOAD_EXTENSIONS = {
    ".csv",
    ".md",
    ".markdown",
    ".txt",
    ".text",
    ".pdf",
    ".docx",
    ".docm",
    ".doc",
    ".pptx",
    ".xlsx",
    ".xls",
}
_ALLOWED_MIME_TYPES = {
    ".csv": {
        "text/csv",
        "text/plain",
        "application/csv",
        "application/vnd.ms-excel",
    },
    ".md": {
        "text/markdown",
        "text/x-markdown",
        "text/plain",
    },
    ".markdown": {
        "text/markdown",
        "text/x-markdown",
        "text/plain",
    },
    ".txt": {"text/plain"},
    ".text": {"text/plain"},
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
        "application/zip",
    },
    ".docm": {
        "application/vnd.ms-word.document.macroenabled.12",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
        "application/zip",
    },
    ".doc": {"application/msword", "application/octet-stream"},
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/octet-stream",
        "application/zip",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
        "application/zip",
    },
    ".xls": {"application/vnd.ms-excel", "application/octet-stream"},
}


@router.post("/upload")
async def upload_source(file: Annotated[UploadFile, File(...)]) -> SourceIngestResponse:
    filename = _validated_upload_filename(file.filename)
    extension = Path(filename).suffix.lower()
    max_upload_bytes = _max_upload_bytes()

    if extension not in _ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported upload type. Allowed: "
                + ", ".join(sorted(_ALLOWED_UPLOAD_EXTENSIONS))
            ),
        )
    if file.size is not None and file.size > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Uploaded file is too large. Maximum allowed size is {max_upload_bytes} bytes.",
        )
    content_type = (file.content_type or "").lower()
    allowed_mime_types = _ALLOWED_MIME_TYPES.get(extension, set())
    if content_type and content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported MIME type '{content_type}' for {extension}. "
                f"Allowed: {', '.join(sorted(allowed_mime_types))}."
            ),
        )

    content = await file.read(max_upload_bytes + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(content) > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Uploaded file is too large. Maximum allowed size is {max_upload_bytes} bytes.",
        )
    try:
        return get_ingestion_service().ingest_upload(
            filename=filename,
            content=content,
        )
    except SourceIngestError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


_ARCHIVE_SUFFIXES = (".zip", ".rar")
_MULTIPART_ARCHIVE_RE = re.compile(r"\.zip\.\d{3}$", re.IGNORECASE)


def _is_archive_filename(filename: str) -> bool:
    lowered = filename.lower()
    return lowered.endswith(_ARCHIVE_SUFFIXES) or bool(_MULTIPART_ARCHIVE_RE.search(lowered))


_MULTIPART_PART_RE = re.compile(r"(\.zip\.\d{3}|\.part\d+\.rar)$", re.IGNORECASE)


def _is_multipart_part(filename: str) -> bool:
    """A single volume of a multipart archive — cannot be expanded alone."""
    return bool(_MULTIPART_PART_RE.search(filename.lower()))


class ArchiveMemberResult(BaseModel):
    member_path: str
    status: str  # ingested | skipped | failed
    reason_code: str | None = None
    source_id: str | None = None


class ArchiveUploadResponse(BaseModel):
    archive: str
    member_count: int
    ingested_count: int
    members: list[ArchiveMemberResult]
    expansion_stats: dict[str, int]


@router.post("/upload-archive")
async def upload_archive(file: Annotated[UploadFile, File(...)]) -> ArchiveUploadResponse:
    """Ingest every supported file inside a .zip / .rar / multipart .zip.NNN archive.

    Reuses the batch expand_archives (zip-slip guard, multipart reassembly) and
    returns a per-member manifest. Each extracted member is held to the same
    per-file size cap as a direct upload, so a decompression bomb cannot exceed
    the configured limit per file.
    """
    filename = _validated_upload_filename(file.filename)
    if not _is_archive_filename(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported archive type. Allowed: .zip, .rar",
        )
    if _is_multipart_part(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Multipart archives (.zip.NNN / .partN.rar) can only be ingested via the "
                "batch tool (scripts/ingest_corpus.py); a single volume cannot be expanded."
            ),
        )
    max_upload_bytes = _max_upload_bytes()
    if file.size is not None and file.size > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Archive is too large. Maximum allowed size is {max_upload_bytes} bytes.",
        )
    content = await file.read(max_upload_bytes + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded archive is empty.",
        )
    if len(content) > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Archive is too large. Maximum allowed size is {max_upload_bytes} bytes.",
        )

    ingestion = get_ingestion_service()
    members: list[ArchiveMemberResult] = []
    ingested = 0
    with tempfile.TemporaryDirectory(prefix="upload_archive_") as work_dir_name:
        work_dir = Path(work_dir_name)
        archive_path = work_dir / Path(filename).name
        archive_path.write_bytes(content)
        extracted, stats = expand_archives([archive_path], work_dir)
        for member in sorted(extracted):
            member_path = str(member.relative_to(work_dir))
            # Check size on disk BEFORE reading the member into memory (a bomb
            # member could be multi-GB — read_bytes first would OOM the process).
            if member.stat().st_size > max_upload_bytes:
                members.append(
                    ArchiveMemberResult(
                        member_path=member_path,
                        status="skipped",
                        reason_code="member_too_large",
                    )
                )
                continue
            member_bytes = member.read_bytes()
            try:
                response = ingestion.ingest_upload(filename=member_path, content=member_bytes)
            except (SourceIngestError, ParserError) as error:
                members.append(
                    ArchiveMemberResult(
                        member_path=member_path,
                        status="failed",
                        reason_code=str(error)[:160],
                    )
                )
                continue
            members.append(
                ArchiveMemberResult(
                    member_path=member_path,
                    status="ingested",
                    source_id=response.source.source_id,
                )
            )
            ingested += 1

    return ArchiveUploadResponse(
        archive=Path(filename).name,
        member_count=len(members),
        ingested_count=ingested,
        members=members,
        expansion_stats={key: int(value) for key, value in stats.items()},
    )


class ImportUrlRequest(BaseModel):
    url: HttpUrl


@router.post("/import-url")
def import_url(request: ImportUrlRequest) -> SourceIngestResponse:
    try:
        return get_ingestion_service().ingest_url(str(request.url))
    except ParserError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except SourceIngestError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{source_id}/enrich")
def enrich_source(source_id: str) -> dict[str, object]:
    """(Re)run extraction+indexing for a source.

    Recovery path for runs stuck in `running` after a restart, and the way to
    re-enrich after dictionary upgrades.
    """
    repository = get_ledger_repository()
    if repository.get_source(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    get_ingestion_service().enrich_source(source_id)
    return {"source_id": source_id, "scheduled": True}


@router.post("/reindex-all")
def reindex_all() -> dict[str, object]:
    """Rebuild the vector index for every source in one batched background pass."""
    import threading

    from nornikel_kg.services.runtime import get_retrieval_service

    service = get_retrieval_service()
    if not service.enabled:
        return {"scheduled": False, "reason": "retrieval index disabled"}
    thread = threading.Thread(target=service.reindex_all, name="reindex-all", daemon=True)
    thread.start()
    return {"scheduled": True}


@router.get("/{source_id}/runs")
def list_source_runs(source_id: str) -> dict[str, list[dict[str, object]]]:
    repository = get_ledger_repository()
    if repository.get_source(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return {"runs": repository.list_ingestion_runs(source_id)}
