"""Merge independently ingested DuckDB shards into one catalog file.

Sharded ingest uses separate `DUCKDB_PATH`s to bypass the single-writer
bottleneck during corpus build. This utility creates/migrates the final
catalog and copies rows from every shard with primary-key conflict tolerance.
Qdrant vectors can be written to a shared collection during ingest; this script
only merges the ledger.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository

TABLES_IN_DEPENDENCY_ORDER = [
    "sources",
    "artifacts",
    "evidence_spans",
    "property_measurements",
    "effect_claims",
    "numeric_facts",
    "entities",
    "entity_aliases",
    "relations",
    "extraction_claims",
    "ingestion_runs",
    "answer_runs",
    "answer_claims",
    "eval_results",
]
TABLES_WITH_CONFLICT_TARGETS = {
    "sources",
    "artifacts",
    "evidence_spans",
    "property_measurements",
    "effect_claims",
    "numeric_facts",
    "entities",
    "entity_aliases",
    "relations",
    "extraction_claims",
    "ingestion_runs",
    "answer_runs",
}


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sql_string(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _columns(connection: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
    # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk.
    return [str(row[1]) for row in rows]


def _count_rows(connection: duckdb.DuckDBPyConnection, table: str) -> int:
    row = connection.execute(f"SELECT count(*) FROM {_quote_identifier(table)}").fetchone()
    if row is None:
        raise RuntimeError(f"count(*) returned no row for {table}")
    return int(row[0])


def merge_shards(output: Path, shards: list[Path]) -> dict[str, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    repository = DuckDBLedgerRepository(output)
    repository.migrate()
    if repository._connection is not None:
        repository._connection.close()
        repository._connection = None

    inserted: dict[str, int] = {table: 0 for table in TABLES_IN_DEPENDENCY_ORDER}
    with duckdb.connect(str(output)) as connection:
        for shard_index, shard in enumerate(shards):
            if not shard.exists():
                raise FileNotFoundError(shard)
            alias = f"shard_{shard_index}"
            connection.execute(
                f"ATTACH {_sql_string(shard)} AS {_quote_identifier(alias)} (READ_ONLY)"
            )
            try:
                connection.execute("BEGIN TRANSACTION")
                for table in TABLES_IN_DEPENDENCY_ORDER:
                    cols = _columns(connection, table)
                    if not cols:
                        continue
                    quoted_cols = ", ".join(_quote_identifier(col) for col in cols)
                    before = _count_rows(connection, table)
                    conflict_clause = (
                        "OR IGNORE " if table in TABLES_WITH_CONFLICT_TARGETS else ""
                    )
                    connection.execute(
                        f"""
                        INSERT {conflict_clause}INTO {_quote_identifier(table)} ({quoted_cols})
                        SELECT {quoted_cols}
                        FROM {_quote_identifier(alias)}.{_quote_identifier(table)}
                        """
                    )
                    after = _count_rows(connection, table)
                    inserted[table] += max(0, after - before)
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            finally:
                connection.execute(f"DETACH {_quote_identifier(alias)}")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Merged DuckDB output path")
    parser.add_argument("shards", nargs="+", help="Shard DuckDB files to merge")
    args = parser.parse_args()

    counts = merge_shards(
        Path(args.output),
        [Path(shard) for shard in args.shards],
    )
    for table, count in counts.items():
        print(f"{table}: +{count}")


if __name__ == "__main__":
    main()
