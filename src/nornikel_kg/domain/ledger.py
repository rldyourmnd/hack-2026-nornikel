from __future__ import annotations

from dataclasses import dataclass

from nornikel_kg.domain.models import EffectClaim, EvidenceSpan, ExperimentRow, PropertyMeasurement


@dataclass(frozen=True)
class EvidenceLedgerPacket:
    evidence: list[EvidenceSpan]
    measurements: list[PropertyMeasurement]
    effects: list[EffectClaim]
    experiments: list[ExperimentRow]
    source_titles: dict[str, str]
    conflicts: list[dict[str, object]]
    gaps: list[dict[str, object]]

    @property
    def measurement(self) -> PropertyMeasurement:
        return next(
            (
                measurement
                for measurement in self.measurements
                if measurement.experiment_id == "exp_nicu_aging_700c_8h"
            ),
            self.measurements[0],
        )

    @property
    def effect(self) -> EffectClaim:
        return next(
            (
                effect
                for effect in self.effects
                if effect.experiment_id == "exp_nicu_aging_700c_8h"
            ),
            self.effects[0],
        )

    @property
    def source_title(self) -> str:
        if not self.source_titles:
            return ""
        return next(iter(self.source_titles.values()))
