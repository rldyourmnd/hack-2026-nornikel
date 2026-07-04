from __future__ import annotations

import re
from typing import Any

from nornikel_kg.domain.models import ExperimentRow
from nornikel_kg.domain.quantities import normalize_unit

_NUMERIC_CONFLICT_THRESHOLD = 0.15
_DIRECTIONS = {"increase", "decrease"}


def _regime_bucket(experiment: ExperimentRow) -> str:
    """Regime key: regime TYPE + temperature, so only near-identical regimes compare.

    The type must survive the `reg_`/`regime_` id prefix. Splitting the raw id
    put every experiment into one `reg:` bucket, so aging and annealing at the
    same temperature produced fake contradictions.
    """
    regime = experiment.regime_id or experiment.regime_summary
    token = regime.removeprefix("reg_").removeprefix("regime_")
    match = re.search(r"(\d{2,4})", token)
    temperature = match.group(1) if match else ""
    prefix = re.split(r"[_\d]", token, maxsplit=1)[0]
    return f"{prefix}:{temperature}"


def _method(experiment: ExperimentRow) -> str:
    return str(experiment.measurement.get("method") or "").strip().lower()


def _value(experiment: ExperimentRow) -> float | None:
    raw = experiment.measurement.get("value")
    if isinstance(raw, int | float):
        return float(raw)
    return None


def _direction(experiment: ExperimentRow) -> str:
    return str(experiment.measurement.get("effect_direction") or "").strip().lower()


class ConflictDetector:
    """Data-driven conflicts over experiments sharing material+property+regime bucket.

    Kinds: opposite effect direction; >15% numeric delta under the SAME method;
    method mismatch that blocks direct numeric comparison.
    """

    def detect(self, experiments: list[ExperimentRow]) -> list[dict[str, object]]:
        groups: dict[tuple[str, str, str], list[ExperimentRow]] = {}
        for experiment in experiments:
            key = (experiment.material_id, experiment.property_id, _regime_bucket(experiment))
            groups.setdefault(key, []).append(experiment)

        conflicts: list[dict[str, object]] = []
        for (material_id, property_id, bucket), members in groups.items():
            if len(members) < 2:
                continue
            for index, left in enumerate(members):
                for right in members[index + 1 :]:
                    if left.experiment_id == right.experiment_id and (
                        left.source_id == right.source_id
                    ):
                        continue
                    conflict = self._compare(left, right, material_id, property_id, bucket)
                    if conflict is not None:
                        conflicts.append(conflict)
        return conflicts

    def _compare(
        self,
        left: ExperimentRow,
        right: ExperimentRow,
        material_id: str,
        property_id: str,
        bucket: str,
    ) -> dict[str, object] | None:
        base = {
            "material_id": material_id,
            "property_id": property_id,
            "regime_bucket": bucket,
            "experiment_ids": [left.experiment_id, right.experiment_id],
            "source_ids": [left.source_id, right.source_id],
            "supporting_span_ids": [*left.evidence_ids, *right.evidence_ids],
        }
        left_direction, right_direction = _direction(left), _direction(right)
        if (
            left_direction in _DIRECTIONS
            and right_direction in _DIRECTIONS
            and left_direction != right_direction
        ):
            return {
                **base,
                "conflict_group_id": f"conf_dir_{left.experiment_id}_{right.experiment_id}",
                "type": "contradictory_direction",
                "summary": (
                    f"{left.material_name}: источники дают противоположный эффект по "
                    f"{left.property_name} при близком режиме "
                    f"({left_direction} против {right_direction})."
                ),
            }
        left_method, right_method = _method(left), _method(right)
        left_value, right_value = _value(left), _value(right)
        if left_method and right_method and left_method != right_method:
            return {
                **base,
                "conflict_group_id": f"conf_method_{left.experiment_id}_{right.experiment_id}",
                "type": "method_mismatch",
                "summary": (
                    f"{left.material_name}: {left.property_name} измерены разными методами "
                    f"({left_method} против {right_method}) — прямое числовое сравнение "
                    "невозможно."
                ),
            }
        left_unit = normalize_unit(str(left.measurement.get("unit") or ""))
        right_unit = normalize_unit(str(right.measurement.get("unit") or ""))
        if (
            left_value is not None
            and right_value is not None
            and left_method
            and left_method == right_method
            and left_unit == right_unit
            and max(abs(left_value), abs(right_value)) > 0
        ):
            delta = abs(left_value - right_value) / max(abs(left_value), abs(right_value))
            if delta > _NUMERIC_CONFLICT_THRESHOLD:
                return {
                    **base,
                    "conflict_group_id": (
                        f"conf_num_{left.experiment_id}_{right.experiment_id}"
                    ),
                    "type": "numeric_disagreement",
                    "summary": (
                        f"{left.material_name}: значения {left.property_name} расходятся на "
                        f"{delta:.0%} при одном методе ({left_value} против {right_value})."
                    ),
                }
        return None


class GapAnalyzer:
    """Coverage matrix material x regime x property against dictionary entities."""

    def coverage(
        self,
        *,
        materials: list[dict[str, Any]],
        regimes: list[dict[str, Any]],
        properties: list[dict[str, Any]],
        experiments: list[ExperimentRow],
    ) -> dict[str, Any]:
        covered: dict[tuple[str, str, str], list[str]] = {}
        for experiment in experiments:
            regime_type = self._regime_type(experiment.regime_id or experiment.regime_summary)
            key = (experiment.material_id, regime_type, experiment.property_id)
            covered.setdefault(key, []).append(experiment.experiment_id)

        cells: list[dict[str, Any]] = []
        for material in materials:
            for regime in regimes:
                regime_type = str(regime["entity_id"]).removeprefix("regime_")
                for prop in properties:
                    key = (str(material["entity_id"]), regime_type, str(prop["entity_id"]))
                    experiment_ids = covered.get(key, [])
                    cells.append(
                        {
                            "material_id": material["entity_id"],
                            "material_name": material["canonical_name"],
                            "regime_type": regime_type,
                            "regime_name": regime["canonical_name"],
                            "property_id": prop["entity_id"],
                            "property_name": prop["canonical_name"],
                            "covered": bool(experiment_ids),
                            "experiment_ids": experiment_ids,
                        }
                    )
        gap_count = sum(1 for cell in cells if not cell["covered"])
        return {
            "materials": [m["canonical_name"] for m in materials],
            "regimes": [r["canonical_name"] for r in regimes],
            "properties": [p["canonical_name"] for p in properties],
            "cells": cells,
            "gap_count": gap_count,
            "covered_count": len(cells) - gap_count,
        }

    def _regime_type(self, regime_id: str) -> str:
        token = regime_id.removeprefix("reg_").removeprefix("regime_")
        return token.split("_")[0]
