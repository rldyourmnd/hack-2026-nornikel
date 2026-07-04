from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import Protocol

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository, SourceIngestError
from nornikel_kg.domain.dates import extract_year, extract_year_from_filename
from nornikel_kg.domain.encoding import decode_text_bytes
from nornikel_kg.domain.geography import detect_geography
from nornikel_kg.domain.ids import source_id_from_bytes, stable_hash
from nornikel_kg.domain.models import SourceIngestResponse
from nornikel_kg.ports.parser import (
    DocumentParserPort,
    NoTextLayerError,
    ParsedBlock,
    ParsedDocument,
    ParserError,
    UrlFetcherPort,
)

logger = logging.getLogger(__name__)

PARSER_EXTENSIONS = {".pdf", ".docx", ".docm", ".pptx"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls"}
LEGACY_DOC_EXTENSIONS = {".doc"}
TEXT_EXTENSIONS = {".csv", ".md", ".markdown", ".txt", ".text"}


class ExtractionServiceProtocol(Protocol):
    def process_source(self, source_id: str) -> dict[str, int]:
        """Extract entities/relations from a source's spans."""


class IndexingServiceProtocol(Protocol):
    def index_source(self, source_id: str) -> int:
        """Index a source's spans into the vector store."""


class IngestionService:
    """Orchestrates source ingestion: parse -> ledger writes -> run lifecycle.

    Parser failures and text-layer-absent PDFs quarantine the source (run row
    with status=quarantined, no evidence spans) instead of surfacing a 500.
    """

    def __init__(
        self,
        repository: DuckDBLedgerRepository,
        *,
        parser: DocumentParserPort | None = None,
        url_fetcher: UrlFetcherPort | None = None,
        artifact_root: Path | None = None,
        extraction_service: ExtractionServiceProtocol | None = None,
        retrieval_service: IndexingServiceProtocol | None = None,
        synchronous_enrichment: bool = True,
    ) -> None:
        self.repository = repository
        self._parser = parser
        self._url_fetcher = url_fetcher
        self._spreadsheet_parser: DocumentParserPort | None = None
        self._legacy_doc_parser: DocumentParserPort | None = None
        self.artifact_root = artifact_root
        self.extraction_service = extraction_service
        self.retrieval_service = retrieval_service
        self.synchronous_enrichment = synchronous_enrichment

    @property
    def parser(self) -> DocumentParserPort:
        if self._parser is None:
            from nornikel_kg.adapters.docling import DoclingDocumentParser

            self._parser = DoclingDocumentParser()
        return self._parser

    @property
    def url_fetcher(self) -> UrlFetcherPort:
        if self._url_fetcher is None:
            from nornikel_kg.adapters.trafilatura import TrafilaturaUrlFetcher

            self._url_fetcher = TrafilaturaUrlFetcher()
        return self._url_fetcher

    @property
    def spreadsheet_parser(self) -> DocumentParserPort:
        if self._spreadsheet_parser is None:
            from nornikel_kg.adapters.spreadsheet import SpreadsheetDocumentParser

            self._spreadsheet_parser = SpreadsheetDocumentParser()
        return self._spreadsheet_parser

    @property
    def legacy_doc_parser(self) -> DocumentParserPort:
        if self._legacy_doc_parser is None:
            from nornikel_kg.adapters.legacy_doc import LegacyDocParser

            self._legacy_doc_parser = LegacyDocParser()
        return self._legacy_doc_parser

    def ingest_upload(
        self,
        *,
        filename: str,
        content: bytes,
        title: str | None = None,
    ) -> SourceIngestResponse:
        extension = Path(filename).suffix.lower()
        if extension in TEXT_EXTENSIONS:
            response = self.repository.ingest_source_bytes(
                filename=filename, content=content, title=title
            )
            self._set_year_geography(
                response.source.source_id,
                filename,
                decode_text_bytes(content)[0][:3000],
            )
            extraction_counters = self._run_extraction(response.source.source_id)
            self._record_run(
                source_id=response.source.source_id,
                status="completed",
                stage="ledger_write",
                counters={
                    "evidence_spans": response.evidence_count,
                    "measurements": response.measurement_count,
                    **extraction_counters,
                },
            )
            return self._with_run_status(response)
        if extension in PARSER_EXTENSIONS:
            return self._ingest_parsed(filename=filename, content=content, title=title)
        if extension in SPREADSHEET_EXTENSIONS:
            return self._ingest_parsed(
                filename=filename,
                content=content,
                title=title,
                parser=self.spreadsheet_parser,
            )
        if extension in LEGACY_DOC_EXTENSIONS:
            return self._ingest_parsed(
                filename=filename,
                content=content,
                title=title,
                parser=self.legacy_doc_parser,
            )
        raise SourceIngestError(f"Unsupported upload extension: {extension}")

    def ingest_url(self, url: str) -> SourceIngestResponse:
        page = self.url_fetcher.fetch(url)
        content = page.text.encode("utf-8")
        source_id = source_id_from_bytes(content)
        parsed = ParsedDocument(
            blocks=[
                ParsedBlock(text=line.strip(), page=None, locator=f"url_block_{index:03d}")
                for index, line in enumerate(page.text.splitlines(), start=1)
                if line.strip()
            ],
            tables=[],
            title=page.title or url,
            parser_profile="trafilatura_v1",
            metadata={
                "url": url,
                **({"date": page.date} if page.date else {}),
            },
        )
        text_spans, table_spans = self.repository.ingest_parsed_document(
            source_id=source_id,
            raw_sha256=hashlib.sha256(content).hexdigest(),
            title=page.title or url,
            document_type="url",
            parsed=parsed,
            artifact_locator=url,
        )
        self._archive_artifact(source_id, "parsed.txt", content)
        self._apply_source_metadata(source_id, url, parsed)
        extraction_counters = self._run_extraction(source_id)
        self._record_run(
            source_id=source_id,
            status="completed",
            stage="ledger_write",
            counters={"evidence_spans": text_spans + table_spans, **extraction_counters},
        )
        return self._response_for(source_id)

    def _ingest_parsed(
        self,
        *,
        filename: str,
        content: bytes,
        title: str | None,
        parser: DocumentParserPort | None = None,
    ) -> SourceIngestResponse:
        source_id = source_id_from_bytes(content)
        raw_sha256 = hashlib.sha256(content).hexdigest()
        document_type = Path(filename).suffix.lower().lstrip(".")
        self._record_run(source_id=source_id, status="running", stage="parse")
        active_parser = parser or self.parser
        try:
            parsed = active_parser.parse(content=content, filename=filename)
        except NoTextLayerError as error:
            self._quarantine(
                source_id, filename, raw_sha256, document_type, str(error),
                reason_code="no_text_layer_ocr_disabled",
            )
            return self._response_for(source_id, warnings=[str(error)])
        except ParserError as error:
            self._quarantine(
                source_id, filename, raw_sha256, document_type, str(error),
                reason_code="parser_error",
            )
            return self._response_for(source_id, warnings=[str(error)])
        except Exception as error:  # never 500 on parser crashes
            logger.exception("Unexpected parser failure for %s", filename)
            self._quarantine(
                source_id, filename, raw_sha256, document_type, repr(error),
                reason_code="unexpected_error",
            )
            return self._response_for(source_id, warnings=[repr(error)])

        self._archive_artifact(source_id, filename, content)
        text_spans, table_spans = self.repository.ingest_parsed_document(
            source_id=source_id,
            raw_sha256=raw_sha256,
            title=title or parsed.title or filename,
            document_type=document_type,
            parsed=parsed,
            artifact_locator=filename,
        )
        self._apply_source_metadata(source_id, filename, parsed)
        self._record_run(
            source_id=source_id,
            status="running",
            stage="extraction",
            counters={"text_spans": text_spans, "table_spans": table_spans},
        )
        self._schedule_enrichment(
            source_id, base_counters={"text_spans": text_spans, "table_spans": table_spans}
        )
        return self._response_for(source_id)

    def enrich_source(self, source_id: str) -> None:
        """(Re)run the enrichment stage for an already-parsed source."""
        self._record_run(source_id=source_id, status="running", stage="extraction")
        self._schedule_enrichment(source_id, base_counters={})

    def _apply_source_metadata(
        self, source_id: str, filename: str, parsed: ParsedDocument
    ) -> None:
        """Year + geography heuristics for query-time filters.

        Year: filename year wins (explicit labeling), else a year-marker-
        guarded scan of the head text (domain.dates — bare numbers like
        «1963 K» no longer masquerade as years). Geography: `ru` when the
        head text is predominantly Cyrillic («ё» included), else `foreign` —
        a coarse but honest split for «отечественная vs зарубежная практика».
        """
        head = " ".join(block.text for block in parsed.blocks[:20])[:3000]
        parsed_date = str(parsed.metadata.get("date") or "")
        fallback_year = extract_year(f"{parsed_date} г.") if parsed_date else None
        self._set_year_geography(source_id, filename, head, fallback_year=fallback_year)

    def _set_year_geography(
        self,
        source_id: str,
        filename: str,
        head: str,
        *,
        fallback_year: int | None = None,
    ) -> None:
        year = extract_year_from_filename(filename) or extract_year(head) or fallback_year
        # Country/affiliation signals beat document language: a Russian-language
        # review of Finnish practice is "foreign", an English Norilsk paper "ru".
        geography = detect_geography(head)
        try:
            self.repository.set_source_metadata(source_id, year=year, geography=geography)
        except Exception:  # metadata is best-effort, never blocks ingest
            logger.warning("Could not set source metadata for %s", source_id, exc_info=True)

    def _schedule_enrichment(self, source_id: str, *, base_counters: dict[str, int]) -> None:
        """Run extraction+indexing off the request thread.

        Real reports carry hundreds of spans; enrichment can take minutes and
        must never hold an HTTP request (or its proxy timeout) hostage. Spans
        are already committed — the run row tracks progress to completed.
        """

        def enrich() -> None:
            # The whole body is guarded: an unhandled error here would kill
            # the daemon thread silently and strand the run in «running»
            # forever (observed live with a litellm dependency error).
            counters = dict(base_counters)
            try:
                counters.update(self._run_extraction(source_id))
            except Exception as error:
                logger.exception("Enrichment failed for %s", source_id)
                self._record_run(
                    source_id=source_id,
                    status="failed",
                    stage="extraction",
                    error=repr(error)[:500],
                    counters=counters,
                )
                return
            self._record_run(
                source_id=source_id,
                status="completed",
                stage="ledger_write",
                counters=counters,
            )

        if self.synchronous_enrichment:
            enrich()
            return
        thread = threading.Thread(
            target=enrich, name=f"enrich-{source_id[:16]}", daemon=True
        )
        thread.start()

    def _quarantine(
        self,
        source_id: str,
        filename: str,
        raw_sha256: str,
        document_type: str,
        error: str,
        *,
        reason_code: str,
    ) -> None:
        # Register the source row so the quarantined state is visible in the UI,
        # but write no evidence spans. The reason_code is a machine-readable
        # prefix so the UI can distinguish "no text layer (OCR off)" from a
        # genuine parser failure without string-matching the message.
        empty = ParsedDocument(blocks=[], tables=[], parser_profile="quarantined")
        self.repository.ingest_parsed_document(
            source_id=source_id,
            raw_sha256=raw_sha256,
            title=filename,
            document_type=document_type,
            parsed=empty,
            artifact_locator=filename,
        )
        self._record_run(
            source_id=source_id,
            status="quarantined",
            stage="parse",
            error=f"[{reason_code}] {error}",
        )

    def _run_extraction(self, source_id: str) -> dict[str, int]:
        """Auto-linking stage; extraction failures never fail the ingest."""
        counters: dict[str, int] = {}
        if self.extraction_service is not None:
            try:
                counters.update(self.extraction_service.process_source(source_id))
            except Exception:
                logger.exception("Extraction failed for %s; spans are still ingested", source_id)
        if self.retrieval_service is not None:
            counters["indexed_units"] = self.retrieval_service.index_source(source_id)
        return counters

    def _record_run(
        self,
        *,
        source_id: str,
        status: str,
        stage: str,
        error: str | None = None,
        counters: dict[str, int] | None = None,
    ) -> None:
        run_id = f"ing_{stable_hash([source_id], 16)}"
        self.repository.record_ingestion_run(
            run_id=run_id,
            source_id=source_id,
            status=status,
            stage=stage,
            error=error,
            counters=counters,
        )

    def _archive_artifact(self, source_id: str, filename: str, content: bytes) -> None:
        if self.artifact_root is None:
            return
        try:
            target_dir = self.artifact_root / "sources" / source_id
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / filename).write_bytes(content)
        except OSError:  # artifact archive is best-effort, never blocks ingest
            logger.warning("Could not archive artifact for %s", source_id, exc_info=True)

    def _response_for(
        self, source_id: str, warnings: list[str] | None = None
    ) -> SourceIngestResponse:
        source = self.repository.get_source(source_id)
        if source is None:
            raise SourceIngestError(f"Source {source_id} was not registered.")
        statuses = self.repository.latest_run_statuses()
        summary = source.model_copy(update={"status": statuses.get(source_id, source.status)})
        return SourceIngestResponse(
            source=summary,
            evidence_count=summary.evidence_count,
            measurement_count=summary.measurement_count,
            warnings=warnings or [],
        )

    def _with_run_status(self, response: SourceIngestResponse) -> SourceIngestResponse:
        statuses = self.repository.latest_run_statuses()
        status = statuses.get(response.source.source_id)
        if status is None:
            return response
        return response.model_copy(
            update={"source": response.source.model_copy(update={"status": status})}
        )
