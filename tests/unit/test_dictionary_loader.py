from pathlib import Path

import duckdb
import pytest

from nornikel_kg.adapters.duckdb.dictionary_loader import load_dictionaries, resolve_alias
from nornikel_kg.domain.normalization import canonical_key

MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "nornikel_kg"
    / "adapters"
    / "duckdb"
    / "migrations"
)


@pytest.fixture()
def connection() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.execute(migration_path.read_text(encoding="utf-8"))
    return conn


def test_canonical_key_normalizes_case_dashes_and_yo() -> None:
    assert canonical_key("  Ni–30Cu ") == "ni-30cu"
    assert canonical_key("МН30") == canonical_key("мн30")
    assert canonical_key("отжёг") == "отжег"
    assert canonical_key("cold   rolling") == "cold rolling"


def test_loader_seeds_all_entity_types(connection: duckdb.DuckDBPyConnection) -> None:
    counts = load_dictionaries(connection)
    assert counts["material"] >= 3
    assert counts["regime"] >= 5
    assert counts["property"] >= 5
    assert counts["equipment"] >= 3
    entity_types = {
        row[0]
        for row in connection.execute("SELECT DISTINCT entity_type FROM entities").fetchall()
    }
    # teams.yml is intentionally empty (no synthetic teams) -> no "team" entities
    assert entity_types == {"material", "regime", "property", "equipment"}


def test_loader_is_idempotent(connection: duckdb.DuckDBPyConnection) -> None:
    load_dictionaries(connection)
    entities_first = connection.execute("SELECT COUNT(*) FROM entities").fetchone()
    aliases_first = connection.execute("SELECT COUNT(*) FROM entity_aliases").fetchone()
    load_dictionaries(connection)
    entities_second = connection.execute("SELECT COUNT(*) FROM entities").fetchone()
    aliases_second = connection.execute("SELECT COUNT(*) FROM entity_aliases").fetchone()
    assert entities_first == entities_second
    assert aliases_first == aliases_second


def test_canonical_and_russian_aliases_resolve(connection: duckdb.DuckDBPyConnection) -> None:
    load_dictionaries(connection)
    assert resolve_alias(connection, "штейн медный") == "mat_matte_copper"
    assert resolve_alias(connection, "файнштейн") == "mat_matte_nickel"
    assert resolve_alias(connection, "старение") == "regime_aging"
    assert resolve_alias(connection, "твердость по Виккерсу") == "prop_vickers_hardness"
    assert resolve_alias(connection, "неизвестный сплав") is None
