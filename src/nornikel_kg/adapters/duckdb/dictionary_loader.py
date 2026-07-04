from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

import duckdb
from nornikel_kg.domain.normalization import canonical_key

DEFAULT_DICTIONARIES_DIR = (
    Path(__file__).resolve().parents[2] / "resources" / "dictionaries"
)


def load_dictionaries(
    connection: duckdb.DuckDBPyConnection,
    dictionaries_dir: Path | None = None,
) -> dict[str, int]:
    """Seed `entities` and `entity_aliases` from the dictionary YAML files.

    Idempotent: rows are keyed by stable dictionary IDs and re-runs upsert the
    same records. Returns per-entity-type seeded counts.
    """
    base_dir = dictionaries_dir or DEFAULT_DICTIONARIES_DIR
    counts: dict[str, int] = {}
    counts["material"] = _seed_materials(connection, base_dir / "materials.yml")
    counts["regime"] = _seed_regimes(connection, base_dir / "regimes.yml")
    counts["property"] = _seed_properties(connection, base_dir / "properties.yml")
    counts["equipment"] = _seed_equipment(connection, base_dir / "equipment.yml")
    counts["team"] = _seed_teams(connection, base_dir / "teams.yml")
    return counts


def resolve_alias(connection: duckdb.DuckDBPyConnection, mention: str) -> str | None:
    """Resolve a mention to an entity_id via canonical key, then alias table."""
    key = canonical_key(mention)
    row = connection.execute(
        "SELECT entity_id FROM entities WHERE canonical_key = ? LIMIT 1", [key]
    ).fetchone()
    if row is not None:
        return str(row[0])
    row = connection.execute(
        "SELECT entity_id FROM entity_aliases WHERE alias_norm = ? LIMIT 1", [key]
    ).fetchone()
    if row is not None:
        return str(row[0])
    return None


def _load_yaml_list(path: Path, root_key: str) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = payload.get(root_key, []) if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _upsert_entity(
    connection: duckdb.DuckDBPyConnection,
    *,
    entity_id: str,
    entity_type: str,
    canonical_name: str,
    metadata: dict[str, Any],
    aliases: list[str],
) -> None:
    connection.execute(
        """
        INSERT INTO entities (entity_id, entity_type, canonical_key, canonical_name, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (entity_id) DO UPDATE SET
          canonical_key = excluded.canonical_key,
          canonical_name = excluded.canonical_name,
          metadata_json = excluded.metadata_json,
          updated_at = now()
        """,
        [
            entity_id,
            entity_type,
            canonical_key(canonical_name),
            canonical_name,
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        ],
    )
    for alias in {canonical_name, *aliases}:
        connection.execute(
            """
            INSERT INTO entity_aliases (alias_norm, entity_id, alias, source)
            VALUES (?, ?, ?, 'dictionary')
            ON CONFLICT (alias_norm, entity_id) DO UPDATE SET alias = excluded.alias
            """,
            [canonical_key(alias), entity_id, alias],
        )


def _seed_materials(connection: duckdb.DuckDBPyConnection, path: Path) -> int:
    items = _load_yaml_list(path, "materials")
    for item in items:
        _upsert_entity(
            connection,
            entity_id=str(item["material_id"]),
            entity_type="material",
            canonical_name=str(item["canonical_name"]),
            metadata={
                "alloy_family": item.get("alloy_family"),
                "composition": item.get("composition", []),
            },
            aliases=[str(alias) for alias in item.get("aliases", [])],
        )
    return len(items)


def _seed_regimes(connection: duckdb.DuckDBPyConnection, path: Path) -> int:
    items = _load_yaml_list(path, "regimes")
    for item in items:
        regime_type = str(item["regime_type"])
        _upsert_entity(
            connection,
            entity_id=f"regime_{regime_type}",
            entity_type="regime",
            canonical_name=str(item["canonical_name"]),
            metadata={"regime_type": regime_type},
            aliases=[str(alias) for alias in item.get("aliases", [])],
        )
    return len(items)


def _seed_properties(connection: duckdb.DuckDBPyConnection, path: Path) -> int:
    items = _load_yaml_list(path, "properties")
    for item in items:
        _upsert_entity(
            connection,
            entity_id=str(item["property_id"]),
            entity_type="property",
            canonical_name=str(item["canonical_name"]),
            metadata={"units": item.get("units", [])},
            aliases=[str(alias) for alias in item.get("aliases", [])],
        )
    return len(items)


def _seed_equipment(connection: duckdb.DuckDBPyConnection, path: Path) -> int:
    items = _load_yaml_list(path, "equipment")
    for item in items:
        _upsert_entity(
            connection,
            entity_id=str(item["equipment_id"]),
            entity_type="equipment",
            canonical_name=str(item["name"]),
            metadata={"lab_id": item.get("lab_id")},
            aliases=[str(alias) for alias in item.get("aliases", [])],
        )
    return len(items)


def _seed_teams(connection: duckdb.DuckDBPyConnection, path: Path) -> int:
    items = _load_yaml_list(path, "teams")
    for item in items:
        _upsert_entity(
            connection,
            entity_id=str(item["team_id"]),
            entity_type="team",
            canonical_name=str(item["name"]),
            metadata={"lab_id": item.get("lab_id")},
            aliases=[str(alias) for alias in item.get("aliases", [])],
        )
    return len(items)
