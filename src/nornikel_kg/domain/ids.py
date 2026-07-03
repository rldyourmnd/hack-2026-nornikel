from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from blake3 import blake3

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_visible_text(value: str) -> str:
    """Normalize evidence text before hashing without changing scientific meaning."""
    return _WHITESPACE_RE.sub(" ", value.strip()).casefold()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(parts: Sequence[Any], length: int = 20) -> str:
    payload = "\x1f".join(
        canonical_json(part) if isinstance(part, Mapping) else str(part) for part in parts
    )
    return blake3(payload.encode("utf-8")).hexdigest(length=length)


def source_id_from_bytes(raw_file_bytes: bytes) -> str:
    return f"src_{blake3(raw_file_bytes).hexdigest(length=16)}"


def artifact_id(
    source_id: str,
    artifact_type: str,
    parser_profile: str,
    artifact_locator: str,
) -> str:
    return f"art_{stable_hash([source_id, artifact_type, parser_profile, artifact_locator], 16)}"


def span_id(
    source_id: str,
    artifact_type: str,
    page_index: int | None,
    stable_locator: str,
    visible_text: str,
    bbox: Sequence[float] | None = None,
) -> str:
    quantized_bbox = None if bbox is None else [round(value, 2) for value in bbox]
    return "evs_" + stable_hash(
        [
            source_id,
            artifact_type,
            page_index if page_index is not None else "none",
            stable_locator,
            quantized_bbox or "no_bbox",
            normalize_visible_text(visible_text),
        ],
        20,
    )


def fact_id(kind: str, payload: Mapping[str, Any]) -> str:
    return f"fact_{stable_hash([kind, payload], 20)}"


def claim_id(payload: Mapping[str, Any]) -> str:
    return f"claim_{stable_hash([payload], 20)}"
