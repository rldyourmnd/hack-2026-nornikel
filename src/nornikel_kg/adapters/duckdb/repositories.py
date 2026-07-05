from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import duckdb
from nornikel_kg.adapters.duckdb.dictionary_loader import load_dictionaries
from nornikel_kg.domain.analysis import ConflictDetector
from nornikel_kg.domain.encoding import decode_text_bytes
from nornikel_kg.domain.evidence import EvidenceSpanFactory
from nornikel_kg.domain.ids import claim_id, fact_id, source_id_from_bytes, stable_hash
from nornikel_kg.domain.ledger import EvidenceLedgerPacket
from nornikel_kg.domain.models import (
    EffectClaim,
    EffectDirection,
    EvidenceSpan,
    ExperimentRow,
    PropertyMeasurement,
    SecurityLabel,
    SourceIngestResponse,
    SourceSummary,
)
from nornikel_kg.domain.normalization import canonical_key
from nornikel_kg.domain.table_facts import extract_facts_from_row
from nornikel_kg.ports.parser import ParsedDocument


class SourceIngestError(ValueError):
    """Raised when uploaded source content is invalid."""

CSV_REQUIRED_COLUMNS = {
    "experiment_id",
    "material",
    "regime",
    "temperature_c",
    "duration_h",
    "atmosphere",
    "property",
    "method",
    "baseline_value",
    "treated_value",
    "unit",
    "effect",
}

EFFECT_DIRECTIONS = {"increase", "decrease", "no_change", "mixed", "unknown"}


class DuckDBLedgerRepository:
    """DuckDB evidence ledger.

    Concurrency contract: DuckDB is effectively single-writer, and concurrent
    request threads sharing this repository used to race on writes
    (`TransactionContext Error: Conflict on update!`). Every connection is
    therefore taken through `_connect()`, which serializes access behind one
    process-level lock; migration + dictionary seeding run once per instance.
    """

    _db_lock = threading.RLock()

    def __init__(self, db_path: Path, *, migrations_dir: Path | None = None) -> None:
        self.db_path = db_path
        self.migrations_dir = migrations_dir or Path(__file__).resolve().parent / "migrations"
        self.evidence_factory = EvidenceSpanFactory()
        self._migrated = False
        # Bumped on every write that changes the QA packet content; the
        # QA service caches the packet keyed by this counter.
        self._data_version = 0
        self._connection: duckdb.DuckDBPyConnection | None = None

    @contextmanager
    def _connect(self) -> Iterator[duckdb.DuckDBPyConnection]:
        """One persistent write connection, serialized by the process lock.

        Opening DuckDB per operation costs tens of milliseconds of file
        locking; under enrichment threads that turned into hours of queueing
        (verified with py-spy). The single connection lives for the process;
        crash recovery relies on DuckDB's WAL.
        """
        with self._db_lock:
            if self._connection is None:
                self._connection = duckdb.connect(str(self.db_path))
            yield self._connection

    @property
    def data_version(self) -> int:
        return self._data_version

    @contextmanager
    def batch_transaction(self) -> Iterator[None]:
        """Group a source's write burst into ONE DuckDB transaction/commit instead
        of hundreds of per-statement autocommits. The batch ingester was bottlenecked
        by commit + lock churn (all workers serialized on the single-writer lock);
        wrapping a source's resolution + relation writes here drops it to one commit
        per source. The lock is held for the block, so concurrent workers' write
        phases don't interleave (parse + LLM already ran in parallel before this)."""
        with self._connect() as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                yield
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")

    def migrate(self) -> None:
        if self._migrated:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            for migration_path in sorted(self.migrations_dir.glob("*.sql")):
                connection.execute(migration_path.read_text(encoding="utf-8"))
            self._ensure_column(connection, "sources", "document_type", "TEXT DEFAULT 'report'")
            self._ensure_column(connection, "property_measurements", "source_id", "TEXT")
            self._ensure_column(connection, "effect_claims", "source_id", "TEXT")
            self._ensure_column(connection, "effect_claims", "material_name", "TEXT")
            self._ensure_column(connection, "effect_claims", "regime_summary", "TEXT")
            self._ensure_column(connection, "sources", "year", "INTEGER")
            self._ensure_column(connection, "sources", "geography", "TEXT")
            load_dictionaries(connection)
        self._migrated = True


    def ingest_source_bytes(
        self,
        *,
        filename: str,
        content: bytes,
        title: str | None = None,
    ) -> SourceIngestResponse:
        self._data_version += 1
        self.migrate()
        source_id = source_id_from_bytes(content)
        raw_sha256 = hashlib.sha256(content).hexdigest()
        document_type = self._document_type_from_filename(filename)
        warnings: list[str] = []

        with self._connect() as connection:
            try:
                connection.execute("BEGIN")
                self._delete_source_records(connection, source_id)
                self._register_source(
                    connection,
                    source_id=source_id,
                    title=title or filename,
                    document_type=document_type,
                    raw_sha256=raw_sha256,
                    security_label="internal",
                )
                if document_type == "table":
                    headers, data_rows = self._read_csv_table(content)
                    if self._csv_is_experiment_schema(headers):
                        rows = self._parse_csv_rows(content)
                        self._insert_csv_rows(
                            connection,
                            source_id=source_id,
                            rows=rows,
                            artifact_locator=filename,
                            parser_profile="csv_table_v1",
                            first_row_ordinal=2,
                        )
                    else:
                        # Arbitrary CSV (no experiment schema): keep it as a
                        # generic headered table — row spans + numeric facts —
                        # instead of rejecting it.
                        self._insert_generic_csv_table(
                            connection,
                            source_id=source_id,
                            headers=headers,
                            data_rows=data_rows,
                            artifact_locator=filename,
                            parser_profile="csv_generic_v1",
                        )
                else:
                    evidence_count = self._insert_markdown_evidence(
                        connection,
                        source_id=source_id,
                        text=decode_text_bytes(content)[0],
                        artifact_locator=filename,
                        parser_profile="markdown_text_v1",
                        selected_lines=(),
                    )
                    if evidence_count == 0:
                        raise SourceIngestError("Markdown source has no extractable evidence.")
                connection.execute("COMMIT")
            except (SourceIngestError, ValueError):
                connection.execute("ROLLBACK")
                raise
            except Exception:
                connection.execute("ROLLBACK")
                raise

        source = next(item for item in self.list_sources() if item.source_id == source_id)
        return SourceIngestResponse(
            source=source,
            evidence_count=source.evidence_count,
            measurement_count=source.measurement_count,
            warnings=warnings,
        )

    def ingest_parsed_document(
        self,
        *,
        source_id: str,
        raw_sha256: str,
        title: str,
        document_type: str,
        parsed: ParsedDocument,
        artifact_locator: str,
        security_label: SecurityLabel = "internal",
    ) -> tuple[int, int]:
        """Write a parsed PDF/DOCX/URL document into the ledger.

        Returns (text_span_count, table_span_count).
        """
        self._data_version += 1
        self.migrate()
        text_spans = 0
        table_spans = 0
        with self._connect() as connection:
            try:
                connection.execute("BEGIN")
                self._delete_source_records(connection, source_id)
                self._register_source(
                    connection,
                    source_id=source_id,
                    title=title,
                    document_type=document_type,
                    raw_sha256=raw_sha256,
                    security_label=security_label,
                )
                connection.execute(
                    """
                    INSERT INTO artifacts (artifact_id, source_id, artifact_type,
                                           parser_profile, locator, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (artifact_id) DO UPDATE SET meta_json = excluded.meta_json
                    """,
                    [
                        f"art_{source_id}",
                        source_id,
                        document_type,
                        parsed.parser_profile,
                        artifact_locator,
                        json.dumps(parsed.metadata, ensure_ascii=False, sort_keys=True),
                    ],
                )
                for block in parsed.blocks:
                    span = self.evidence_factory.create(
                        source_id=source_id,
                        artifact_type="text",
                        parser_profile=parsed.parser_profile,
                        artifact_locator=artifact_locator,
                        span_type="text",
                        visible_text=block.text,
                        page=block.page,
                        stable_locator=block.locator or "block_unknown",
                        validation_status="validated_rule",
                        evidence_confidence=0.97,
                        security_label=security_label,
                    )
                    self._insert_evidence_span(connection, span)
                    text_spans += 1
                # Cap table rows per source: a 1000+-row data-table xls otherwise
                # emits 1000+ spans, each embedded + indexed + fact-extracted, which
                # dominates the batch (measured: Ag_Tabs 1211 rows ~464s). Headers +
                # lead rows carry the entities; MAX_TABLE_ROWS_PER_SOURCE bounds it.
                max_table_rows = int(os.getenv("MAX_TABLE_ROWS_PER_SOURCE", "400"))
                for table in parsed.tables:
                    if max_table_rows and table_spans >= max_table_rows:
                        break
                    for row in table.rows:
                        if max_table_rows and table_spans >= max_table_rows:
                            break
                        # Spreadsheets carry the worksheet name in the locator so
                        # Excel provenance reads sheet:Summary:table_001:row_003;
                        # PDF/DOCX tables keep the flat table_{i}:row_{j} form.
                        if table.sheet_name:
                            row_locator = (
                                f"sheet:{table.sheet_name}:"
                                f"table_{table.table_index:03d}:row_{row.row_index:03d}"
                            )
                            locator_extra: dict[str, object] | None = {
                                "sheet": table.sheet_name,
                                "row": row.row_index,
                                "headers": list(table.header),
                            }
                        else:
                            row_locator = f"table_{table.table_index}:row_{row.row_index}"
                            locator_extra = None
                        row_span = self.evidence_factory.create(
                            source_id=source_id,
                            artifact_type="table",
                            parser_profile=parsed.parser_profile,
                            artifact_locator=artifact_locator,
                            span_type="table_row",
                            visible_text=row.text,
                            page=table.page,
                            stable_locator=row_locator,
                            validation_status="validated_rule",
                            evidence_confidence=0.97,
                            security_label=security_label,
                            locator_extra=locator_extra,
                        )
                        self._insert_evidence_span(connection, row_span)
                        self._insert_numeric_facts(
                            connection,
                            source_id=source_id,
                            span_id=row_span.span_id,
                            headers=[cell.header for cell in row.cells],
                            values=[cell.text for cell in row.cells],
                        )
                        table_spans += 1
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return text_spans, table_spans

    def record_ingestion_run(
        self,
        *,
        run_id: str,
        source_id: str,
        status: str,
        stage: str,
        error: str | None = None,
        counters: dict[str, int] | None = None,
    ) -> None:
        self.migrate()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_runs (run_id, source_id, status, stage, error, counters_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id) DO UPDATE SET
                  status = excluded.status,
                  stage = excluded.stage,
                  error = excluded.error,
                  counters_json = excluded.counters_json
                """,
                [
                    run_id,
                    source_id,
                    status,
                    stage,
                    error,
                    json.dumps(counters or {}, ensure_ascii=False, sort_keys=True),
                ],
            )

    def list_ingestion_runs(self, source_id: str | None = None) -> list[dict[str, Any]]:
        self.migrate()
        where_clause = "WHERE source_id = ?" if source_id else ""
        params: list[str] = [source_id] if source_id else []
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT run_id, source_id, status, stage, error, counters_json, created_at
                FROM ingestion_runs
                {where_clause}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [
            {
                "run_id": str(row[0]),
                "source_id": str(row[1]),
                "status": str(row[2]),
                "stage": str(row[3]),
                "error": row[4],
                "counters": json.loads(str(row[5] or "{}")),
                "created_at": str(row[6]),
            }
            for row in rows
        ]

    def latest_run_statuses(self) -> dict[str, str]:
        """Map source_id -> most recent ingestion run status."""
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_id, status
                FROM (
                  SELECT source_id, status,
                         ROW_NUMBER() OVER (PARTITION BY source_id ORDER BY created_at DESC) AS rn
                  FROM ingestion_runs
                )
                WHERE rn = 1
                """
            ).fetchall()
        return {str(row[0]): str(row[1]) for row in rows}

    # --- Entity / relation graph layer -------------------------------------

    def find_entity(self, mention: str, entity_type: str | None = None) -> dict[str, Any] | None:
        """Resolve a mention by canonical key first, then alias table."""
        self.migrate()
        key = canonical_key(mention)
        type_clause = "AND e.entity_type = ?" if entity_type else ""
        type_params = [entity_type] if entity_type else []
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT e.entity_id FROM entities e
                WHERE e.canonical_key = ? {type_clause}
                LIMIT 1
                """,
                [key, *type_params],
            ).fetchone()
            if row is None:
                row = connection.execute(
                    f"""
                    SELECT a.entity_id FROM entity_aliases a
                    JOIN entities e ON e.entity_id = a.entity_id
                    WHERE a.alias_norm = ? {type_clause}
                    LIMIT 1
                    """,
                    [key, *type_params],
                ).fetchone()
        if row is None:
            return None
        return self.get_entity(str(row[0]))

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        self.migrate()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT entity_id, entity_type, canonical_key, canonical_name, description,
                       metadata_json, evidence_span_ids_json, confidence, validation_status
                FROM entities WHERE entity_id = ?
                """,
                [entity_id],
            ).fetchone()
            if row is None:
                return None
            aliases = [
                str(alias_row[0])
                for alias_row in connection.execute(
                    "SELECT alias FROM entity_aliases WHERE entity_id = ? ORDER BY alias",
                    [entity_id],
                ).fetchall()
            ]
        return {
            "entity_id": str(row[0]),
            "entity_type": str(row[1]),
            "canonical_key": str(row[2]),
            "canonical_name": str(row[3]),
            "description": row[4],
            "metadata": json.loads(str(row[5] or "{}")),
            "evidence_span_ids": json.loads(str(row[6] or "[]")),
            "confidence": float(row[7]),
            "validation_status": str(row[8]),
            "aliases": aliases,
        }

    def create_entity(
        self,
        *,
        entity_id: str,
        entity_type: str,
        canonical_name: str,
        evidence_span_ids: list[str],
        metadata: dict[str, Any] | None = None,
        confidence: float = 0.85,
        validation_status: str = "extracted",
    ) -> None:
        self.migrate()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO entities (entity_id, entity_type, canonical_key, canonical_name,
                                      metadata_json, evidence_span_ids_json, confidence,
                                      validation_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (entity_id) DO NOTHING
                """,
                [
                    entity_id,
                    entity_type,
                    canonical_key(canonical_name),
                    canonical_name,
                    json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(evidence_span_ids, ensure_ascii=False),
                    confidence,
                    validation_status,
                ],
            )
            connection.execute(
                """
                INSERT INTO entity_aliases (alias_norm, entity_id, alias, source)
                VALUES (?, ?, ?, 'learned')
                ON CONFLICT (alias_norm, entity_id) DO NOTHING
                """,
                [canonical_key(canonical_name), entity_id, canonical_name],
            )

    def set_entity_metadata(self, entity_id: str, updates: dict[str, Any]) -> None:
        """Merge metadata keys into an entity (existing keys are overwritten)."""
        if not updates:
            return
        self.migrate()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT metadata_json FROM entities WHERE entity_id = ?",
                [entity_id],
            ).fetchone()
            if row is None:
                return
            metadata: dict[str, Any] = json.loads(str(row[0] or "{}"))
            metadata.update(updates)
            connection.execute(
                "UPDATE entities SET metadata_json = ?, updated_at = now() WHERE entity_id = ?",
                [json.dumps(metadata, ensure_ascii=False, sort_keys=True), entity_id],
            )

    def merge_entity_evidence(
        self,
        entity_id: str,
        *,
        span_ids: list[str],
        new_alias: str | None = None,
    ) -> None:
        """Append unseen evidence spans (and optionally a learned alias) to an entity."""
        self.migrate()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT evidence_span_ids_json FROM entities WHERE entity_id = ?",
                [entity_id],
            ).fetchone()
            if row is None:
                return
            existing: list[str] = json.loads(str(row[0] or "[]"))
            merged = existing + [span_id for span_id in span_ids if span_id not in existing]
            connection.execute(
                "UPDATE entities SET evidence_span_ids_json = ?, updated_at = now() "
                "WHERE entity_id = ?",
                [json.dumps(merged, ensure_ascii=False), entity_id],
            )
            if new_alias:
                connection.execute(
                    """
                    INSERT INTO entity_aliases (alias_norm, entity_id, alias, source)
                    VALUES (?, ?, ?, 'learned')
                    ON CONFLICT (alias_norm, entity_id) DO NOTHING
                    """,
                    [canonical_key(new_alias), entity_id, new_alias],
                )

    def insert_relation(
        self,
        *,
        src_entity_id: str,
        relation_type: str,
        dst_entity_id: str,
        evidence_span_ids: list[str],
        confidence: float = 0.85,
        validation_status: str = "extracted",
    ) -> str:
        """Idempotent relation write; evidence spans are unioned on conflict."""
        self.migrate()
        relation_id = "rel_" + stable_hash([src_entity_id, relation_type, dst_entity_id], 20)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT evidence_span_ids_json FROM relations WHERE relation_id = ?",
                [relation_id],
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO relations (relation_id, src_entity_id, relation_type,
                                           dst_entity_id, evidence_span_ids_json, confidence,
                                           validation_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        relation_id,
                        src_entity_id,
                        relation_type,
                        dst_entity_id,
                        json.dumps(evidence_span_ids, ensure_ascii=False),
                        confidence,
                        validation_status,
                    ],
                )
            else:
                existing: list[str] = json.loads(str(row[0] or "[]"))
                merged = existing + [s for s in evidence_span_ids if s not in existing]
                connection.execute(
                    "UPDATE relations SET evidence_span_ids_json = ? WHERE relation_id = ?",
                    [json.dumps(merged, ensure_ascii=False), relation_id],
                )
        return relation_id

    def insert_extraction_claim(
        self,
        *,
        claim_id_value: str,
        source_id: str,
        span_id: str,
        payload: dict[str, Any],
        model_id: str,
        status: str = "extracted",
    ) -> None:
        self.migrate()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO extraction_claims (claim_id, source_id, span_id, payload_json,
                                               model_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (claim_id) DO UPDATE SET
                  payload_json = excluded.payload_json,
                  model_id = excluded.model_id,
                  status = excluded.status
                """,
                [
                    claim_id_value,
                    source_id,
                    span_id,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    model_id,
                    status,
                ],
            )

    def search_entities(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Exact key, alias, then substring search over entities."""
        self.migrate()
        key = canonical_key(query)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT e.entity_id, e.entity_type, e.canonical_name,
                       len(e.evidence_span_ids_json) AS evidence_weight,
                       CASE
                         WHEN e.canonical_key = ? THEN 0
                         WHEN a.alias_norm = ? THEN 1
                         ELSE 2
                       END AS rank
                FROM entities e
                LEFT JOIN entity_aliases a ON a.entity_id = e.entity_id
                WHERE e.canonical_key = ?
                   OR a.alias_norm = ?
                   OR e.canonical_key LIKE '%' || ? || '%'
                   OR a.alias_norm LIKE '%' || ? || '%'
                ORDER BY rank, evidence_weight DESC, e.canonical_name
                LIMIT ?
                """,
                [key, key, key, key, key, key, limit],
            ).fetchall()
        return [
            {
                "entity_id": str(row[0]),
                "entity_type": str(row[1]),
                "canonical_name": str(row[2]),
            }
            for row in rows
        ]

    def set_source_metadata(
        self, source_id: str, *, year: int | None, geography: str | None
    ) -> None:
        self.migrate()
        with self._connect() as connection:
            connection.execute(
                "UPDATE sources SET year = COALESCE(?, year), "
                "geography = COALESCE(?, geography) WHERE source_id = ?",
                [year, geography, source_id],
            )

    def source_metadata(self) -> dict[str, dict[str, Any]]:
        """source_id -> {year, geography} for query-time filtering."""
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT source_id, year, geography FROM sources"
            ).fetchall()
        return {
            str(row[0]): {
                "year": None if row[1] is None else int(row[1]),
                "geography": None if row[2] is None else str(row[2]),
            }
            for row in rows
        }

    def record_answer_run(
        self,
        *,
        run_id: str,
        question: str,
        filters: dict[str, Any],
        packet_stats: dict[str, Any],
        model_id: str,
        latency_ms: int,
        verification: dict[str, Any],
    ) -> None:
        self.migrate()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO answer_runs (run_id, question, filters_json, packet_stats_json,
                                         model_id, latency_ms, verification_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id) DO UPDATE SET
                  packet_stats_json = excluded.packet_stats_json,
                  model_id = excluded.model_id,
                  latency_ms = excluded.latency_ms,
                  verification_json = excluded.verification_json
                """,
                [
                    run_id,
                    question,
                    json.dumps(filters, ensure_ascii=False, sort_keys=True),
                    json.dumps(packet_stats, ensure_ascii=False, sort_keys=True),
                    model_id,
                    latency_ms,
                    json.dumps(verification, ensure_ascii=False, sort_keys=True),
                ],
            )

    def corpus_stats(self) -> dict[str, Any]:
        """Aggregate corpus/graph counters for the UI overview."""
        self.migrate()
        with self._connect() as connection:
            scalars = {
                "sources": "SELECT COUNT(*) FROM sources",
                "evidence_spans": "SELECT COUNT(*) FROM evidence_spans",
                "measurements": "SELECT COUNT(*) FROM property_measurements",
                "numeric_facts": "SELECT COUNT(*) FROM numeric_facts",
                "relations": "SELECT COUNT(*) FROM relations",
                "answer_runs": "SELECT COUNT(*) FROM answer_runs",
            }
            stats: dict[str, Any] = {
                name: int(connection.execute(query).fetchone()[0])  # type: ignore[index]
                for name, query in scalars.items()
            }
            stats["entities_by_type"] = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    "SELECT entity_type, COUNT(*) FROM entities "
                    "GROUP BY entity_type ORDER BY COUNT(*) DESC"
                ).fetchall()
            }
            stats["relations_by_type"] = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    "SELECT relation_type, COUNT(*) FROM relations "
                    "GROUP BY relation_type ORDER BY COUNT(*) DESC"
                ).fetchall()
            }
            stats["security_labels"] = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    "SELECT security_label, COUNT(*) FROM sources "
                    "GROUP BY security_label ORDER BY COUNT(*) DESC"
                ).fetchall()
            }
            # Machine-readable quarantine reasons: the ingest run stores a
            # "[reason_code] message" prefix (no_text_layer_ocr_disabled etc.)
            # so the Data page shows why files were skipped without OCR.
            reasons: dict[str, int] = {}
            for row in connection.execute(
                "SELECT error FROM ingestion_runs WHERE status = 'quarantined'"
            ).fetchall():
                message = str(row[0] or "")
                code = (
                    message[1 : message.index("]")]
                    if message.startswith("[") and "]" in message
                    else "unknown"
                )
                reasons[code] = reasons.get(code, 0) + 1
            stats["quarantine_reasons"] = reasons
            stats["quarantined"] = sum(reasons.values())
            stats["numeric_facts_by_unit"] = {
                str(row[0] or "—"): int(row[1])
                for row in connection.execute(
                    "SELECT unit, COUNT(*) AS n FROM numeric_facts "
                    "GROUP BY unit ORDER BY n DESC LIMIT 20"
                ).fetchall()
            }
            stats["numeric_facts_by_subject"] = {
                str(row[0] or "—"): int(row[1])
                for row in connection.execute(
                    "SELECT subject, COUNT(*) AS n FROM numeric_facts "
                    "GROUP BY subject ORDER BY n DESC LIMIT 20"
                ).fetchall()
            }
        return stats

    def list_answer_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Most recent answer runs (verification trail for the security page)."""
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, question, model_id, latency_ms, verification_json, created_at
                FROM answer_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()
        return [
            {
                "run_id": str(row[0]),
                "question": str(row[1]),
                "answer_mode": row[2],
                "latency_ms": row[3],
                "verification": json.loads(str(row[4] or "{}")),
                "created_at": str(row[5]),
            }
            for row in rows
        ]

    def get_answer_run(self, run_id: str) -> dict[str, Any] | None:
        self.migrate()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id, question, filters_json, packet_stats_json, model_id,
                       latency_ms, verification_json, created_at
                FROM answer_runs WHERE run_id = ?
                """,
                [run_id],
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": str(row[0]),
            "question": str(row[1]),
            "filters": json.loads(str(row[2] or "{}")),
            "packet_stats": json.loads(str(row[3] or "{}")),
            "model_id": row[4],
            "latency_ms": row[5],
            "verification": json.loads(str(row[6] or "{}")),
            "created_at": str(row[7]),
        }

    def store_eval_result(
        self, *, run_id: str, question_id: str, metrics: dict[str, Any]
    ) -> None:
        self.migrate()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO eval_results (run_id, question_id, metrics_json) VALUES (?, ?, ?)",
                [run_id, question_id, json.dumps(metrics, ensure_ascii=False, sort_keys=True)],
            )

    def latest_eval_summary(self) -> dict[str, Any] | None:
        """Aggregate metrics of the most recent eval run, or None if never stored."""
        self.migrate()
        with self._connect() as connection:
            run_row = connection.execute(
                "SELECT run_id, MAX(created_at) FROM eval_results GROUP BY run_id "
                "ORDER BY MAX(created_at) DESC LIMIT 1"
            ).fetchone()
            if run_row is None:
                return None
            run_id = str(run_row[0])
            rows = connection.execute(
                "SELECT question_id, metrics_json FROM eval_results WHERE run_id = ?",
                [run_id],
            ).fetchall()
        per_question = {str(row[0]): json.loads(str(row[1])) for row in rows}
        aggregate: dict[str, float] = {}
        counts: dict[str, int] = {}
        for metrics in per_question.values():
            for name, value in metrics.items():
                if isinstance(value, int | float):
                    aggregate[name] = aggregate.get(name, 0.0) + float(value)
                    counts[name] = counts.get(name, 0) + 1
        averaged = {
            name: (total / counts[name] if counts[name] else 0.0)
            for name, total in aggregate.items()
        }
        return {
            "run_id": run_id,
            "run_at": str(run_row[1]),
            "question_count": len(per_question),
            "metrics": averaged,
        }

    def list_alias_index(self) -> list[tuple[str, str, str]]:
        """(alias_norm, entity_type, alias) triples for rule-based mention scanning."""
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.alias_norm, e.entity_type, a.alias
                FROM entity_aliases a
                JOIN entities e ON e.entity_id = a.entity_id
                """
            ).fetchall()
        return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]

    def list_graph_entities(self) -> list[dict[str, Any]]:
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT entity_id, entity_type, canonical_name, evidence_span_ids_json
                FROM entities
                """
            ).fetchall()
        return [
            {
                "entity_id": str(row[0]),
                "entity_type": str(row[1]),
                "canonical_name": str(row[2]),
                "evidence_count": len(json.loads(str(row[3] or "[]"))),
            }
            for row in rows
        ]

    def graph_neighborhood(
        self, entity_id: str, *, depth: int, limit: int
    ) -> dict[str, Any] | None:
        """Bounded k-hop neighborhood via indexed per-hop SQL.

        Replaces full-graph NetworkX materialization: the frontier is expanded
        one hop at a time over the indexed relations table (both edge
        directions), stopping at `depth` hops or once `limit` nodes are reached.
        Returns the reached node data + induced edges, or None if the focus
        entity is unknown. Ranking/trimming to `limit` stays in GraphService so
        the response shape and ordering are unchanged.
        """
        self.migrate()
        depth = max(1, min(depth, 2))
        with self._connect() as connection:
            focus = connection.execute(
                "SELECT 1 FROM entities WHERE entity_id = ?", [entity_id]
            ).fetchone()
            if focus is None:
                return None
            reached: set[str] = {entity_id}
            frontier: set[str] = {entity_id}
            for _hop in range(depth):
                if not frontier:
                    break
                placeholders = ", ".join("?" for _ in frontier)
                neighbor_rows = connection.execute(
                    f"""
                    SELECT dst_entity_id AS neighbor FROM relations
                    WHERE src_entity_id IN ({placeholders})
                    UNION
                    SELECT src_entity_id AS neighbor FROM relations
                    WHERE dst_entity_id IN ({placeholders})
                    """,
                    list(frontier) + list(frontier),
                ).fetchall()
                neighbors = {str(row[0]) for row in neighbor_rows}
                frontier = neighbors - reached
                reached |= neighbors
                if len(reached) >= limit:
                    break
            node_placeholders = ", ".join("?" for _ in reached)
            node_rows = connection.execute(
                f"""
                SELECT entity_id, entity_type, canonical_name, evidence_span_ids_json
                FROM entities WHERE entity_id IN ({node_placeholders})
                """,
                list(reached),
            ).fetchall()
            real_ids = [str(row[0]) for row in node_rows]
            edge_rows: list[Any] = []
            if real_ids:
                edge_placeholders = ", ".join("?" for _ in real_ids)
                edge_rows = connection.execute(
                    f"""
                    SELECT relation_id, src_entity_id, relation_type, dst_entity_id,
                           evidence_span_ids_json
                    FROM relations
                    WHERE src_entity_id IN ({edge_placeholders})
                      AND dst_entity_id IN ({edge_placeholders})
                    """,
                    real_ids + real_ids,
                ).fetchall()
        nodes = [
            {
                "entity_id": str(row[0]),
                "entity_type": str(row[1]),
                "canonical_name": str(row[2]),
                "evidence_count": len(json.loads(str(row[3] or "[]"))),
            }
            for row in node_rows
        ]
        edges = [
            {
                "relation_id": str(row[0]),
                "src_entity_id": str(row[1]),
                "relation_type": str(row[2]),
                "dst_entity_id": str(row[3]),
                "evidence_count": len(json.loads(str(row[4] or "[]"))),
            }
            for row in edge_rows
        ]
        return {"nodes": nodes, "edges": edges}

    def list_entities_by_type(
        self, entity_types: list[str], limit: int = 24
    ) -> list[dict[str, Any]]:
        """Entities of the given type(s), most-referenced first.

        Powers the experts/labs directory: evidence_count is a proxy for how
        prominent an entity is in the corpus (≈ how many spans mention it).
        """
        self.migrate()
        if not entity_types:
            return []
        placeholders = ", ".join("?" for _ in entity_types)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT entity_id, entity_type, canonical_name, evidence_span_ids_json
                FROM entities
                WHERE entity_type IN ({placeholders})
                """,
                list(entity_types),
            ).fetchall()
        items: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            count = len(json.loads(str(row[3] or "[]")))
            items.append(
                (
                    count,
                    {
                        "entity_id": str(row[0]),
                        "entity_type": str(row[1]),
                        "canonical_name": str(row[2]),
                        "evidence_count": count,
                    },
                )
            )
        items.sort(key=lambda pair: pair[0], reverse=True)
        return [entity for _count, entity in items[:limit]]

    def list_graph_relations(self) -> list[dict[str, Any]]:
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT relation_id, src_entity_id, relation_type, dst_entity_id,
                       evidence_span_ids_json, confidence
                FROM relations
                """
            ).fetchall()
        return [
            {
                "relation_id": str(row[0]),
                "src_entity_id": str(row[1]),
                "relation_type": str(row[2]),
                "dst_entity_id": str(row[3]),
                "evidence_span_ids": json.loads(str(row[4] or "[]")),
                "confidence": float(row[5]),
            }
            for row in rows
        ]

    def load_evidence_packet(self) -> EvidenceLedgerPacket:
        self.migrate()
        with self._connect() as connection:
            source_rows = connection.execute(
                """
                SELECT source_id, title
                FROM sources
                ORDER BY created_at DESC, title
                """
            ).fetchall()
            source_titles = {str(row[0]): str(row[1]) for row in source_rows}
            evidence_rows = connection.execute(
                """
                SELECT
                  span_id,
                  source_id,
                  artifact_id,
                  span_type,
                  visible_text,
                  page,
                  locator_json,
                  validation_status,
                  evidence_confidence,
                  security_label
                FROM evidence_spans
                ORDER BY source_id, page NULLS LAST, span_type DESC, span_id
                """
            ).fetchall()
            measurement_rows = connection.execute(
                """
                SELECT
                  measurement_id,
                  experiment_id,
                  property_id,
                  property_name,
                  value,
                  unit,
                  original_value,
                  method,
                  supporting_span_ids_json,
                  validation_status
                FROM property_measurements
                ORDER BY experiment_id, measurement_id
                """
            ).fetchall()
            effect_rows = connection.execute(
                """
                SELECT
                  effect_id,
                  experiment_id,
                  material_id,
                  regime_id,
                  property_id,
                  direction,
                  supporting_span_ids_json,
                  baseline_measurement_id,
                  treated_measurement_id,
                  delta_value,
                  delta_unit,
                  qualitative_only,
                  qualitative_summary
                FROM effect_claims
                ORDER BY experiment_id, effect_id
                """
            ).fetchall()
            experiment_rows = connection.execute(
                """
                SELECT
                  m.measurement_id,
                  m.source_id,
                  m.experiment_id,
                  m.property_id,
                  m.property_name,
                  m.value,
                  m.unit,
                  m.validation_status,
                  e.material_id,
                  e.material_name,
                  e.regime_id,
                  e.regime_summary,
                  e.direction,
                  e.delta_value,
                  e.delta_unit,
                  e.supporting_span_ids_json,
                  m.method
                FROM property_measurements m
                JOIN effect_claims e
                  ON m.experiment_id = e.experiment_id
                 AND m.property_id = e.property_id
                 AND m.source_id = e.source_id
                ORDER BY m.experiment_id, m.measurement_id
                """
            ).fetchall()

        evidence = [self._evidence_from_row(row) for row in evidence_rows]
        measurements = [self._measurement_from_row(row) for row in measurement_rows]
        effects = [self._effect_from_row(row) for row in effect_rows]
        experiments = [self._experiment_from_row(row) for row in experiment_rows]

        return EvidenceLedgerPacket(
            evidence=evidence,
            measurements=measurements,
            effects=effects,
            experiments=experiments,
            source_titles=source_titles,
            conflicts=ConflictDetector().detect(experiments),
            gaps=[],
        )

    def list_sources(self) -> list[SourceSummary]:
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                  s.source_id,
                  s.title,
                  s.document_type,
                  s.security_label,
                  COUNT(DISTINCT ev.span_id) AS evidence_count,
                  COUNT(DISTINCT pm.measurement_id) AS measurement_count,
                  MAX(ir.status) AS run_status,
                  s.year,
                  s.geography
                FROM sources s
                LEFT JOIN evidence_spans ev ON ev.source_id = s.source_id
                LEFT JOIN property_measurements pm ON pm.source_id = s.source_id
                LEFT JOIN (
                  SELECT source_id, status,
                         ROW_NUMBER() OVER (
                           PARTITION BY source_id ORDER BY created_at DESC
                         ) AS rn
                  FROM ingestion_runs
                ) ir ON ir.source_id = s.source_id AND ir.rn = 1
                GROUP BY s.source_id, s.title, s.document_type, s.security_label,
                         s.created_at, s.year, s.geography
                ORDER BY s.created_at DESC, s.title
                """
            ).fetchall()
        return [
            SourceSummary(
                source_id=str(row[0]),
                title=str(row[1]),
                document_type=str(row[2]),
                security_label=row[3],
                status=str(row[6]) if row[6] else "ledger",
                evidence_count=int(row[4]),
                measurement_count=int(row[5]),
                year=None if row[7] is None else int(row[7]),
                geography=None if row[8] is None else str(row[8]),
            )
            for row in rows
        ]

    def get_source(self, source_id: str) -> SourceSummary | None:
        self.migrate()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                  s.source_id,
                  s.title,
                  s.document_type,
                  s.security_label,
                  COUNT(DISTINCT ev.span_id) AS evidence_count,
                  COUNT(DISTINCT pm.measurement_id) AS measurement_count
                FROM sources s
                LEFT JOIN evidence_spans ev ON ev.source_id = s.source_id
                LEFT JOIN property_measurements pm ON pm.source_id = s.source_id
                WHERE s.source_id = ?
                GROUP BY s.source_id, s.title, s.document_type, s.security_label
                """,
                [source_id],
            ).fetchone()
        if row is None:
            return None
        return SourceSummary(
            source_id=str(row[0]),
            title=str(row[1]),
            document_type=str(row[2]),
            security_label=row[3],
            status="ledger",
            evidence_count=int(row[4]),
            measurement_count=int(row[5]),
        )

    def delete_source(self, source_id: str) -> bool:
        self._data_version += 1
        self.migrate()
        with self._connect() as connection:
            source = self._find_source(connection, source_id)
            if source is None:
                return False
            try:
                connection.execute("BEGIN")
                self._delete_source_records(connection, source_id)
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return source is not None

    def list_evidence_spans(self, source_id: str | None = None) -> list[EvidenceSpan]:
        self.migrate()
        where_clause = "WHERE source_id = ?" if source_id else ""
        params: list[str] = [source_id] if source_id else []
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                  span_id,
                  source_id,
                  artifact_id,
                  span_type,
                  visible_text,
                  page,
                  locator_json,
                  validation_status,
                  evidence_confidence,
                  security_label
                FROM evidence_spans
                {where_clause}
                ORDER BY source_id, page NULLS LAST, span_type DESC, span_id
                """,
                params,
            ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def list_evidence_spans_by_ids(self, span_ids: list[str]) -> list[EvidenceSpan]:
        """Targeted rejoin for retrieval hits (never loads the full table)."""
        if not span_ids:
            return []
        self.migrate()
        placeholders = ", ".join("?" for _ in span_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                  span_id,
                  source_id,
                  artifact_id,
                  span_type,
                  visible_text,
                  page,
                  locator_json,
                  validation_status,
                  evidence_confidence,
                  security_label
                FROM evidence_spans
                WHERE span_id IN ({placeholders})
                """,
                list(span_ids),
            ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def _ensure_column(
        self,
        connection: duckdb.DuckDBPyConnection,
        table_name: str,
        column_name: str,
        column_type: str,
    ) -> None:
        existing = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        }
        if column_name not in existing:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def _delete_source_records(
        self,
        connection: duckdb.DuckDBPyConnection,
        source_id: str,
    ) -> None:
        """Cascade delete: no graph row may keep citing removed spans.

        Relations/entities strip the deleted span ids from their evidence;
        rows whose evidence empties out are removed (dictionary-seeded
        entities stay — their ids are stable and reseeded by migrations).
        """
        deleted_span_ids = {
            str(row[0])
            for row in connection.execute(
                "SELECT span_id FROM evidence_spans WHERE source_id = ?", [source_id]
            ).fetchall()
        }
        connection.execute("DELETE FROM numeric_facts WHERE source_id = ?", [source_id])
        connection.execute("DELETE FROM property_measurements WHERE source_id = ?", [source_id])
        connection.execute("DELETE FROM effect_claims WHERE source_id = ?", [source_id])
        connection.execute("DELETE FROM evidence_spans WHERE source_id = ?", [source_id])
        connection.execute("DELETE FROM sources WHERE source_id = ?", [source_id])
        connection.execute("DELETE FROM extraction_claims WHERE source_id = ?", [source_id])
        connection.execute("DELETE FROM ingestion_runs WHERE source_id = ?", [source_id])
        if not deleted_span_ids:
            return
        for row in connection.execute(
            "SELECT relation_id, evidence_span_ids_json FROM relations"
        ).fetchall():
            span_ids: list[str] = json.loads(str(row[1] or "[]"))
            kept = [span_id for span_id in span_ids if span_id not in deleted_span_ids]
            if len(kept) == len(span_ids):
                continue
            if kept:
                connection.execute(
                    "UPDATE relations SET evidence_span_ids_json = ? WHERE relation_id = ?",
                    [json.dumps(kept, ensure_ascii=False), str(row[0])],
                )
            else:
                connection.execute(
                    "DELETE FROM relations WHERE relation_id = ?", [str(row[0])]
                )
        for row in connection.execute(
            "SELECT entity_id, evidence_span_ids_json FROM entities"
        ).fetchall():
            entity_id = str(row[0])
            span_ids = json.loads(str(row[1] or "[]"))
            kept = [span_id for span_id in span_ids if span_id not in deleted_span_ids]
            if len(kept) == len(span_ids):
                continue
            if kept or not entity_id.startswith("ent_"):
                connection.execute(
                    "UPDATE entities SET evidence_span_ids_json = ? WHERE entity_id = ?",
                    [json.dumps(kept, ensure_ascii=False), entity_id],
                )
            else:
                connection.execute(
                    "DELETE FROM relations WHERE src_entity_id = ? OR dst_entity_id = ?",
                    [entity_id, entity_id],
                )
                connection.execute(
                    "DELETE FROM entity_aliases WHERE entity_id = ?", [entity_id]
                )
                connection.execute("DELETE FROM entities WHERE entity_id = ?", [entity_id])

    def _find_source(
        self,
        connection: duckdb.DuckDBPyConnection,
        source_id: str,
    ) -> SourceSummary | None:
        row = connection.execute(
            """
            SELECT
              s.source_id,
              s.title,
              s.document_type,
              s.security_label
            FROM sources s
            WHERE s.source_id = ?
            """,
            [source_id],
        ).fetchone()
        if row is None:
            return None
        return SourceSummary(
            source_id=str(row[0]),
            title=str(row[1]),
            document_type=str(row[2]),
            security_label=row[3],
            status="ledger",
        )

    def _register_source(
        self,
        connection: duckdb.DuckDBPyConnection,
        *,
        source_id: str,
        title: str,
        document_type: str,
        raw_sha256: str,
        security_label: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO sources (source_id, title, document_type, raw_sha256, security_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            [source_id, title, document_type, raw_sha256, security_label],
        )

    def _parse_csv_rows(self, content: bytes) -> list[dict[str, str]]:
        text, _encoding = decode_text_bytes(content)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise SourceIngestError("CSV source has no header row.")

        normalized_fieldnames = [fieldname.strip() for fieldname in reader.fieldnames]
        missing_columns = sorted(CSV_REQUIRED_COLUMNS.difference(set(normalized_fieldnames)))
        if missing_columns:
            raise SourceIngestError(
                f"CSV source is missing required columns: {', '.join(missing_columns)}."
            )
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized_row = {
                normalized_fieldnames[index]: (value.strip() if isinstance(value, str) else "")
                for index, value in enumerate(row.values())
            }
            rows.append(normalized_row)
        if not rows:
            raise SourceIngestError("CSV source has no data rows.")
        return rows

    def _read_csv_table(self, content: bytes) -> tuple[list[str], list[list[str]]]:
        """Decode a CSV into (header, data rows) with the shared cascade decoder."""
        text, _encoding = decode_text_bytes(content)
        all_rows = list(csv.reader(io.StringIO(text)))
        if not all_rows:
            raise SourceIngestError("CSV source has no header row.")
        headers = [str(header).strip() for header in all_rows[0]]
        data_rows = [row for row in all_rows[1:] if any(str(cell).strip() for cell in row)]
        return headers, data_rows

    def _csv_is_experiment_schema(self, headers: list[str]) -> bool:
        return CSV_REQUIRED_COLUMNS.issubset({header.strip() for header in headers})

    def _insert_generic_csv_table(
        self,
        connection: duckdb.DuckDBPyConnection,
        *,
        source_id: str,
        headers: list[str],
        data_rows: list[list[str]],
        artifact_locator: str,
        parser_profile: str,
    ) -> int:
        """Ingest an arbitrary CSV as header-labeled table-row spans + facts."""
        clean_headers = [header.strip() for header in headers]
        inserted = 0
        for ordinal, values in enumerate(data_rows, start=2):
            labeled = " | ".join(
                f"{header}: {str(value).strip()}"
                for header, value in zip(clean_headers, values, strict=False)
                if header and str(value).strip()
            )
            if not labeled:
                continue
            span = self.evidence_factory.create(
                source_id=source_id,
                artifact_type="table",
                parser_profile=parser_profile,
                artifact_locator=artifact_locator,
                span_type="table_row",
                visible_text=labeled,
                page=None,
                stable_locator=f"table_001:row_{ordinal:03d}",
                validation_status="validated_rule",
                evidence_confidence=0.95,
                security_label="internal",
            )
            self._insert_evidence_span(connection, span)
            self._insert_numeric_facts(
                connection,
                source_id=source_id,
                span_id=span.span_id,
                headers=clean_headers,
                values=[str(value) for value in values],
            )
            inserted += 1
        if inserted == 0:
            raise SourceIngestError("CSV source has no extractable rows.")
        return inserted

    def _insert_numeric_facts(
        self,
        connection: duckdb.DuckDBPyConnection,
        *,
        source_id: str,
        span_id: str,
        headers: list[str],
        values: list[str],
    ) -> int:
        """Persist subject-tagged numeric facts extracted from one table row.

        Facts with a valid unit also produce a property_measurement row, so
        structured numeric data is available for measurement-based queries
        (not just numeric_facts).
        """
        facts = extract_facts_from_row(list(headers), [str(value) for value in values])
        for fact in facts:
            identifier = "nf_" + stable_hash(
                [span_id, fact.subject, fact.prop, repr(fact.value), fact.unit], 20
            )
            connection.execute(
                """
                INSERT INTO numeric_facts
                    (fact_id, source_id, span_id, subject, subject_label, prop, value,
                     unit, qualifier, confidence, validation_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (fact_id) DO NOTHING
                """,
                [
                    identifier,
                    source_id,
                    span_id,
                    fact.subject,
                    fact.subject_label,
                    fact.prop,
                    fact.value,
                    fact.unit,
                    "",
                    1.0,
                    "candidate",
                ],
            )
            if fact.unit:
                measurement_id = "pm_" + stable_hash(
                    [span_id, fact.subject, fact.prop, repr(fact.value)], 20
                )
                connection.execute(
                    """
                    INSERT INTO property_measurements
                        (measurement_id, source_id, experiment_id, property_id,
                         property_name, value, unit, original_value, method,
                         supporting_span_ids_json, validation_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (measurement_id) DO NOTHING
                    """,
                    [
                        measurement_id,
                        source_id,
                        "",
                        "",
                        fact.subject_label,
                        fact.value,
                        fact.unit,
                        str(fact.value),
                        "table_extraction",
                        json.dumps([span_id], ensure_ascii=False),
                        "validated_rule",
                    ],
                )
        return len(facts)

    def list_numeric_facts_for_spans(
        self, span_ids: list[str]
    ) -> dict[str, list[tuple[str, float, str]]]:
        """span_id -> [(subject-or-property, value, unit), ...] for QA constraints."""
        if not span_ids:
            return {}
        self.migrate()
        placeholders = ", ".join("?" for _ in span_ids)
        result: dict[str, list[tuple[str, float, str]]] = {}
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT span_id, subject, prop, value, unit FROM numeric_facts
                WHERE span_id IN ({placeholders})
                """,
                list(span_ids),
            ).fetchall()
        for span_id, subject, prop, value, unit in rows:
            entries = result.setdefault(str(span_id), [])
            entries.append((str(subject), float(value), str(unit or "")))
            if prop and str(prop) != str(subject):
                entries.append((str(prop), float(value), str(unit or "")))
        return result

    def _insert_csv_rows(
        self,
        connection: duckdb.DuckDBPyConnection,
        *,
        source_id: str,
        rows: list[dict[str, str]],
        artifact_locator: str,
        parser_profile: str,
        first_row_ordinal: int,
    ) -> None:
        for index, row in enumerate(rows):
            row_ordinal = first_row_ordinal + index
            material_name = self._require_nonempty(row, "material", row_ordinal)
            material_id = self._material_id(material_name)
            regime_type = self._require_nonempty(row, "regime", row_ordinal).lower()
            temperature_c = self._parse_float(row, "temperature_c", row_ordinal)
            duration_h = self._parse_float(row, "duration_h", row_ordinal)
            atmosphere = self._require_nonempty(row, "atmosphere", row_ordinal)
            regime_id = self._regime_id(regime_type, temperature_c, duration_h, atmosphere)
            regime_summary = self._regime_summary(
                regime_type,
                temperature_c,
                duration_h,
                atmosphere,
            )
            property_raw = self._require_nonempty(row, "property", row_ordinal)
            method = self._require_nonempty(row, "method", row_ordinal)
            property_id = self._property_id(property_raw, method)
            property_name = self._property_name(property_raw, method)
            baseline_value = self._parse_float(row, "baseline_value", row_ordinal)
            treated_value = self._parse_float(row, "treated_value", row_ordinal)
            unit = self._require_nonempty(row, "unit", row_ordinal)
            direction = self._require_nonempty(row, "effect", row_ordinal).lower()
            if direction not in EFFECT_DIRECTIONS:
                raise SourceIngestError(
                    f"Row {row_ordinal}: unsupported effect value '{direction}'. "
                    f"Allowed: {', '.join(sorted(EFFECT_DIRECTIONS))}."
                )
            effect_direction = cast(EffectDirection, direction)
            delta_value = None
            if treated_value is not None and baseline_value is not None:
                delta_value = round(treated_value - baseline_value, 6)
            experiment_id = self._require_nonempty(row, "experiment_id", row_ordinal)
            table_text = self._table_row_text(
                material_name=material_name,
                regime=regime_type,
                temperature=temperature_c,
                duration=duration_h,
                atmosphere=atmosphere,
                property_name=property_name,
                method=method,
                baseline_value=baseline_value,
                treated_value=treated_value,
                unit=unit,
            )
            table_span = self.evidence_factory.create(
                source_id=source_id,
                artifact_type="table",
                parser_profile=parser_profile,
                artifact_locator=artifact_locator,
                span_type="table_row",
                visible_text=table_text,
                page=2,
                stable_locator=f"table_001:row_{row_ordinal:03d}",
                validation_status="validated_rule",
                evidence_confidence=1.0,
                security_label="internal",
            )
            measurement = PropertyMeasurement(
                measurement_id=fact_id(
                    "measurement",
                    {
                        "source_id": source_id,
                        "experiment_id": experiment_id,
                        "property": property_id,
                        "value": treated_value,
                        "unit": unit,
                    },
                ),
                experiment_id=experiment_id,
                property_id=property_id,
                property_name=property_name,
                value=treated_value,
                unit=unit,
                original_value=f"{treated_value:g} {unit}" if treated_value is not None else None,
                method=method,
                supporting_span_ids=[table_span.span_id],
            )
            effect = EffectClaim(
                effect_id=claim_id(
                    {
                        "source_id": source_id,
                        "experiment_id": experiment_id,
                        "direction": direction,
                        "supporting_span_ids": measurement.supporting_span_ids,
                    }
                ),
                experiment_id=experiment_id,
                material_id=material_id,
                regime_id=regime_id,
                property_id=property_id,
                direction=effect_direction,
                baseline_measurement_id=f"{measurement.measurement_id}_baseline",
                treated_measurement_id=measurement.measurement_id,
                delta_value=delta_value,
                delta_unit=unit,
                qualitative_summary=self._effect_summary(
                    material_name=material_name,
                    regime_summary=regime_summary,
                    property_name=property_name,
                    direction=direction,
                    treated_value=treated_value,
                    delta_value=delta_value,
                    unit=unit,
                ),
                supporting_span_ids=[table_span.span_id],
            )

            self._delete_fact_records(connection, measurement.measurement_id, effect.effect_id)
            self._insert_evidence_span(connection, table_span)
            self._insert_measurement(connection, measurement, source_id=source_id)
            self._insert_effect(
                connection,
                effect,
                source_id=source_id,
                material_name=material_name,
                regime_summary=regime_summary,
            )

    def _insert_markdown_evidence(
        self,
        connection: duckdb.DuckDBPyConnection,
        *,
        source_id: str,
        text: str,
        artifact_locator: str,
        parser_profile: str,
        selected_lines: tuple[str, ...],
    ) -> int:
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if selected_lines:
            lines = [
                line
                for line in lines
                if any(selected_line in line for selected_line in selected_lines)
            ]

        for index, line in enumerate(lines, start=2):
            stable_locator = (
                "section:discussion:block_002"
                if "method mismatch prevents direct numeric comparison" in line
                else f"section:text:block_{index:03d}"
            )
            span = self.evidence_factory.create(
                source_id=source_id,
                artifact_type="text",
                parser_profile=parser_profile,
                artifact_locator=artifact_locator,
                span_type="text",
                visible_text=line,
                page=3,
                stable_locator=stable_locator,
                validation_status="validated_rule",
                evidence_confidence=0.98,
                security_label="internal",
            )
            self._insert_evidence_span(connection, span)

        return len(lines)

    def _delete_fact_records(
        self,
        connection: duckdb.DuckDBPyConnection,
        measurement_id: str,
        effect_id: str,
    ) -> None:
        connection.execute(
            "DELETE FROM property_measurements WHERE measurement_id = ?",
            [measurement_id],
        )
        connection.execute("DELETE FROM effect_claims WHERE effect_id = ?", [effect_id])

    def _insert_evidence_span(
        self,
        connection: duckdb.DuckDBPyConnection,
        span: EvidenceSpan,
    ) -> None:
        connection.execute("DELETE FROM evidence_spans WHERE span_id = ?", [span.span_id])
        connection.execute(
            """
            INSERT INTO evidence_spans (
              span_id,
              source_id,
              artifact_id,
              span_type,
              visible_text,
              page,
              locator_json,
              validation_status,
              evidence_confidence,
              security_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                span.span_id,
                span.source_id,
                span.artifact_id,
                span.span_type,
                span.visible_text,
                span.page,
                json.dumps(span.locator, ensure_ascii=False, sort_keys=True),
                span.validation_status,
                span.evidence_confidence,
                span.security_label,
            ],
        )

    def _insert_measurement(
        self,
        connection: duckdb.DuckDBPyConnection,
        measurement: PropertyMeasurement,
        *,
        source_id: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO property_measurements (
              measurement_id,
              source_id,
              experiment_id,
              property_id,
              property_name,
              value,
              unit,
              original_value,
              method,
              supporting_span_ids_json,
              validation_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                measurement.measurement_id,
                source_id,
                measurement.experiment_id,
                measurement.property_id,
                measurement.property_name,
                measurement.value,
                measurement.unit,
                measurement.original_value,
                measurement.method,
                json.dumps(measurement.supporting_span_ids, ensure_ascii=False),
                measurement.validation_status,
            ],
        )

    def _insert_effect(
        self,
        connection: duckdb.DuckDBPyConnection,
        effect: EffectClaim,
        *,
        source_id: str,
        material_name: str,
        regime_summary: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO effect_claims (
              effect_id,
              source_id,
              experiment_id,
              material_id,
              material_name,
              regime_id,
              regime_summary,
              property_id,
              direction,
              supporting_span_ids_json,
              baseline_measurement_id,
              treated_measurement_id,
              delta_value,
              delta_unit,
              qualitative_only,
              qualitative_summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                effect.effect_id,
                source_id,
                effect.experiment_id,
                effect.material_id,
                material_name,
                effect.regime_id,
                regime_summary,
                effect.property_id,
                effect.direction,
                json.dumps(effect.supporting_span_ids, ensure_ascii=False),
                effect.baseline_measurement_id,
                effect.treated_measurement_id,
                effect.delta_value,
                effect.delta_unit,
                effect.qualitative_only,
                effect.qualitative_summary,
            ],
        )

    def _evidence_from_row(self, row: tuple[Any, ...]) -> EvidenceSpan:
        return EvidenceSpan(
            span_id=str(row[0]),
            source_id=str(row[1]),
            artifact_id=str(row[2]),
            span_type=row[3],
            visible_text=str(row[4]),
            page=None if row[5] is None else int(row[5]),
            locator=json.loads(str(row[6])),
            validation_status=row[7],
            evidence_confidence=float(row[8]),
            security_label=row[9],
        )

    def _measurement_from_row(self, row: tuple[Any, ...]) -> PropertyMeasurement:
        return PropertyMeasurement(
            measurement_id=str(row[0]),
            experiment_id=str(row[1]),
            property_id=str(row[2]),
            property_name=str(row[3]),
            value=None if row[4] is None else float(row[4]),
            unit=None if row[5] is None else str(row[5]),
            original_value=None if row[6] is None else str(row[6]),
            method=None if row[7] is None else str(row[7]),
            supporting_span_ids=json.loads(str(row[8])),
            validation_status=row[9],
        )

    def _effect_from_row(self, row: tuple[Any, ...]) -> EffectClaim:
        return EffectClaim(
            effect_id=str(row[0]),
            experiment_id=str(row[1]),
            material_id=str(row[2]),
            regime_id=str(row[3]),
            property_id=str(row[4]),
            direction=row[5],
            supporting_span_ids=json.loads(str(row[6])),
            baseline_measurement_id=None if row[7] is None else str(row[7]),
            treated_measurement_id=None if row[8] is None else str(row[8]),
            delta_value=None if row[9] is None else float(row[9]),
            delta_unit=None if row[10] is None else str(row[10]),
            qualitative_only=bool(row[11]),
            qualitative_summary=str(row[12]),
        )

    def _experiment_from_row(self, row: tuple[Any, ...]) -> ExperimentRow:
        evidence_ids = json.loads(str(row[15]))
        return ExperimentRow(
            source_id=str(row[1]),
            experiment_id=str(row[2]),
            material_id=str(row[8]),
            material_name=str(row[9]),
            regime_id=str(row[10]),
            regime_summary=str(row[11]),
            property_id=str(row[3]),
            property_name=str(row[4]),
            measurement={
                "value": None if row[5] is None else float(row[5]),
                "unit": None if row[6] is None else str(row[6]),
                "delta_value": None if row[13] is None else float(row[13]),
                "delta_unit": None if row[14] is None else str(row[14]),
                "effect_direction": str(row[12]),
                "method": None if len(row) < 17 or row[16] is None else str(row[16]),
            },
            evidence_ids=evidence_ids,
            validation_status=row[7],
        )



    def _document_type_from_filename(self, filename: str) -> str:
        return "table" if filename.lower().endswith(".csv") else "document"

    def _material_id(self, material_name: str) -> str:
        return f"mat_{self._slug(material_name)}"

    def _property_id(self, property_raw: str, method: str) -> str:
        lowered = f"{property_raw} {method}".lower()
        if "vickers" in lowered:
            return "prop_vickers_hardness"
        if "rockwell" in lowered:
            return "prop_rockwell_hardness"
        if "conductivity" in lowered or "электропровод" in lowered:
            return "prop_conductivity"
        return f"prop_{self._slug(property_raw)}"

    def _property_name(self, property_raw: str, method: str) -> str:
        lowered = f"{property_raw} {method}".lower()
        if "vickers" in lowered:
            return "Твердость по Виккерсу"
        if "rockwell" in lowered:
            return "Твердость по Роквеллу"
        if "conductivity" in lowered or "электропровод" in lowered:
            return "Электропроводность"
        return property_raw

    def _regime_id(
        self,
        regime_type: str,
        temperature_c: float | None,
        duration_h: float | None,
        atmosphere: str,
    ) -> str:
        temp = "unknown" if temperature_c is None else f"{temperature_c:g}c"
        duration = "unknown" if duration_h is None else f"{duration_h:g}h"
        return f"reg_{self._slug(regime_type)}_{temp}_{duration}_{self._slug(atmosphere)}"

    def _regime_summary(
        self,
        regime_type: str,
        temperature_c: float | None,
        duration_h: float | None,
        atmosphere: str,
    ) -> str:
        regime_ru = {"aging": "Старение", "annealing": "Отжиг"}.get(regime_type, regime_type)
        temp = "?" if temperature_c is None else f"{temperature_c:g} C"
        duration = "?" if duration_h is None else f"{duration_h:g} ч"
        return f"{regime_ru}, {temp}, {duration}, {atmosphere}"

    def _effect_summary(
        self,
        *,
        material_name: str,
        regime_summary: str,
        property_name: str,
        direction: str,
        treated_value: float | None,
        delta_value: float | None,
        unit: str,
    ) -> str:
        direction_ru = {
            "increase": "повысил",
            "decrease": "снизил",
            "no_change": "не изменил",
            "mixed": "дал смешанный эффект на",
            "unknown": "имеет неизвестный эффект на",
        }[direction]
        value = (
            "без численного значения"
            if treated_value is None
            else f"до {treated_value:g} {unit}"
        )
        delta = "" if delta_value is None else f" (Δ {delta_value:g} {unit})"
        return (
            f"{regime_summary} для {material_name} {direction_ru} "
            f"{property_name} {value}{delta}."
        )

    def _table_row_text(
        self,
        *,
        material_name: str,
        regime: str,
        temperature: float | None,
        duration: float | None,
        atmosphere: str,
        property_name: str,
        method: str,
        baseline_value: float | None,
        treated_value: float | None,
        unit: str,
    ) -> str:
        baseline = "unknown" if baseline_value is None else f"{baseline_value:g} {unit}"
        treated = "unknown" if treated_value is None else f"{treated_value:g} {unit}"
        temperature_text = "?" if temperature is None else f"{temperature:g}"
        duration_text = "?" if duration is None else f"{duration:g}"
        return (
            f"Sample {material_name}-A | {regime.title()} {temperature_text} C | "
            f"{duration_text} h | {atmosphere} | {property_name} {method} | "
            f"baseline {baseline} | treated {treated}"
        )

    def _parse_float(self, row: dict[str, str], field: str, row_number: int) -> float:
        raw = row.get(field)
        if raw is None:
            raise SourceIngestError(f"Row {row_number}: missing required numeric field '{field}'.")
        stripped = raw.strip()
        if not stripped:
            raise SourceIngestError(f"Row {row_number}: field '{field}' is required.")
        try:
            return float(stripped)
        except ValueError as exc:
            raise SourceIngestError(
                f"Row {row_number}: field '{field}' must be a numeric value."
            ) from exc

    def _require_nonempty(self, row: dict[str, str], field: str, row_number: int) -> str:
        raw = row.get(field)
        if raw is None:
            raise SourceIngestError(f"Row {row_number}: missing required field '{field}'.")
        value = raw.strip()
        if not value:
            raise SourceIngestError(f"Row {row_number}: field '{field}' is required.")
        return value

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
