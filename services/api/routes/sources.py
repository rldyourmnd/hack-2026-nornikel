from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl

from nornikel_kg.adapters.duckdb.repositories import SourceIngestError
from nornikel_kg.domain.models import EvidenceSpan, SourceIngestResponse, SourceSummary
from nornikel_kg.ports.parser import ParserError
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
                ".csv, .md, .markdown, .txt, .text, .pdf, .docx, .docm, .doc, .xlsx, .xls"
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
                f"Unsupported MIME type '{content_type}'. "
                "Allowed: text/csv, text/plain, text/markdown, text/x-markdown."
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
