from __future__ import annotations

import contextlib
import re
import time
from difflib import SequenceMatcher
from typing import Any, Literal, Protocol

from nornikel_kg.domain.answer_claims import ClaimVerifier
from nornikel_kg.domain.dates import parse_time_scope
from nornikel_kg.domain.ids import stable_hash
from nornikel_kg.domain.ledger import EvidenceLedgerPacket
from nornikel_kg.domain.models import (
    AnswerSentence,
    AskFilters,
    AskRequest,
    AskResponse,
    EvidenceSpan,
    ExperimentRow,
    GraphPath,
)
from nornikel_kg.domain.quantities import (
    facts_satisfy_constraints,
    parse_numeric_constraints,
    parse_parameter_constraints,
    satisfies_constraints,
)
from nornikel_kg.domain.security import SourceLabelPolicy
from nornikel_kg.domain.table_facts import parse_labeled_span_facts
from nornikel_kg.ports.ledger import EvidenceLedgerPort

MATERIAL_ELEMENTS = frozenset({"ni", "cu", "cr", "mo", "al", "fe", "co", "mn", "ti"})
MATERIAL_TOKEN_RE = re.compile(r"\b[a-z]{1,8}\d{1,3}[a-z0-9]*\b", re.IGNORECASE)
# Alloy codes are element-symbol sequences with digits; anything else («CO2»,
# «Al2O3», «section3») is NOT a requested material (audit C4: such tokens
# silently blanked whole answers).
_ALLOY_TOKEN_RE = re.compile(
    r"(?:(?:ni|cu|cr|mo|al|fe|co|mn|ti))+\d{1,3}(?:(?:ni|cu|cr|mo|al|fe|co|mn|ti)|\d)*"
)
_CHEMICAL_FORMULA_VETO = frozenset(
    {"co2", "co3", "al2", "mn2", "fe2", "fe3", "ti2", "cu2", "ni2"}
)
MATERIAL_ELEMENT_PATTERN = r"(?:ni|cu|cr|mo|al|fe|co|mn|ti)"
MATERIAL_SEPARATOR_PATTERN = r"[\s\-_/–—]*"
MATERIAL_SPACED_TOKEN_RE = re.compile(
    rf"\b{MATERIAL_ELEMENT_PATTERN}"
    rf"(?:{MATERIAL_SEPARATOR_PATTERN}{MATERIAL_ELEMENT_PATTERN})*"
    rf"{MATERIAL_SEPARATOR_PATTERN}\d{{1,3}}"
    rf"(?:{MATERIAL_SEPARATOR_PATTERN}{MATERIAL_ELEMENT_PATTERN})*\b",
    re.IGNORECASE,
)


class RetrievalServiceProtocol(Protocol):
    def retrieve_span_ids(
        self,
        *,
        question: str,
        allowed_labels: list[str],
        source_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[str]:
        """Hybrid-retrieval span candidates."""


class AnswerComposerProtocol(Protocol):
    def compose(
        self,
        *,
        question: str,
        experiments: list[ExperimentRow],
        evidence: list[EvidenceSpan],
        fallback_summary: list[AnswerSentence],
        run_id: str,
        source_context: dict[str, str] | None = None,
    ) -> tuple[list[AnswerSentence], str]:
        """LLM answer synthesis with deterministic fallback."""


class RunRecorderProtocol(Protocol):
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
        """Persist replayable answer-run metadata."""

    def source_metadata(self) -> dict[str, dict[str, Any]]:
        """source_id -> {year, geography} for scope filters."""


class EvidenceQAService:
    """Deterministic evidence-led QA over the current DuckDB ledger packet."""

    def __init__(
        self,
        *,
        claim_verifier: ClaimVerifier | None = None,
        source_label_policy: SourceLabelPolicy | None = None,
        ledger_repository: EvidenceLedgerPort | None = None,
        retrieval_service: RetrievalServiceProtocol | None = None,
        answer_composer: AnswerComposerProtocol | None = None,
        run_recorder: RunRecorderProtocol | None = None,
    ) -> None:
        self.claim_verifier = claim_verifier or ClaimVerifier()
        self.source_label_policy = source_label_policy or SourceLabelPolicy()
        self.ledger_repository = ledger_repository
        self.retrieval_service = retrieval_service
        self.answer_composer = answer_composer
        self.run_recorder = run_recorder
        self._packet_cache: tuple[int, EvidenceLedgerPacket] | None = None

    def ask(self, request: AskRequest) -> AskResponse:
        started = time.perf_counter()
        packet = self._load_packet()
        filters = self._effective_filters(request)
        # Explicit UI year filters are strict; a scope derived from question
        # text keeps unknown-year sources (not knowing the year is not the
        # same as being out of range).
        strict_years = request.filters is not None and (
            request.filters.year_from is not None or request.filters.year_to is not None
        )
        allowed_evidence = self.source_label_policy.filter_spans(packet.evidence)
        allowed_span_ids = {span.span_id for span in allowed_evidence}
        unmatched_material_tokens = self._unmatched_material_tokens(
            question=request.question,
            experiments=packet.experiments,
        )
        selected_experiments = self._select_experiments(
            question=request.question,
            experiments=packet.experiments,
            request_filters=filters,
        )
        selected_experiments = [
            experiment
            for experiment in selected_experiments
            if any(span_id in allowed_span_ids for span_id in experiment.evidence_ids)
        ]
        selected_experiments = self._apply_source_scope(
            selected_experiments, filters, keep_unknown_year=not strict_years
        )
        selected_experiments = self._apply_numeric_constraints(
            request.question, selected_experiments
        )
        selected_evidence = self._evidence_for_experiments(allowed_evidence, selected_experiments)
        selected_evidence = self._augment_with_retrieval(
            request=request,
            allowed_evidence=allowed_evidence,
            selected_evidence=selected_evidence,
        )
        selected_evidence = self._apply_scope_to_evidence(
            selected_evidence, filters, keep_unknown_year=not strict_years
        )
        selected_evidence = self._drop_constraint_violating_evidence(
            request.question, selected_evidence
        )
        graph_paths = [
            self._graph_path_for_experiment(experiment, selected_evidence)
            for experiment in selected_experiments
        ]
        summary = [
            self._answer_sentence_for_experiment(experiment, graph_paths[index])
            for index, experiment in enumerate(selected_experiments)
        ]
        run_id = f"qa_run_{stable_hash([request.question, request.language], 12)}"
        answer_mode = "deterministic"
        if self.answer_composer is not None and selected_evidence:
            summary, answer_mode = self.answer_composer.compose(
                question=request.question,
                experiments=selected_experiments,
                evidence=selected_evidence,
                fallback_summary=summary,
                run_id=run_id,
                source_context=self._source_context(packet, selected_evidence),
            )
        verification = self.claim_verifier.verify(
            answer_summary=summary,
            evidence_spans=selected_evidence,
            source_label_policy=self.source_label_policy,
        )
        conflicts = self._conflicts_for_question(
            request.question, packet.conflicts, selected_experiments
        )
        gaps = self._gaps_for_question(
            question=request.question,
            packet_gaps=packet.gaps,
            selected_experiments=selected_experiments,
            unmatched_material_tokens=unmatched_material_tokens,
        )
        follow_up_queries = self._follow_up_queries(
            question=request.question,
            experiments=packet.experiments,
            unmatched_material_tokens=unmatched_material_tokens,
        )
        response = AskResponse(
            run_id=run_id,
            answer_summary=summary,
            confidence=self._confidence_level(
                request.question, selected_experiments, summary, selected_evidence
            ),
            experiments=selected_experiments,
            evidence=selected_evidence,
            graph_paths=graph_paths if request.include_graph else [],
            verification=verification,
            conflicts=conflicts,
            gaps=gaps if request.include_gaps else [],
            follow_up_queries=follow_up_queries,
        )
        if self.run_recorder is not None:
            latency_ms = int((time.perf_counter() - started) * 1000)
            # Run metadata must never break answers.
            with contextlib.suppress(Exception):
                self.run_recorder.record_answer_run(
                    run_id=run_id,
                    question=request.question,
                    filters=filters.model_dump(exclude_none=True) if filters else {},
                    packet_stats={
                        "experiments": len(selected_experiments),
                        "evidence": len(selected_evidence),
                        "answer_mode": answer_mode,
                    },
                    model_id=answer_mode,
                    latency_ms=latency_ms,
                    verification=verification.model_dump(),
                )
        return response

    def _scope_predicate(
        self,
        filters: AskFilters,
        metadata: dict[str, dict[str, Any]],
        *,
        keep_unknown_year: bool,
    ) -> Any:
        def keeps(source_id: str | None) -> bool:
            meta = metadata.get(source_id or "", {})
            if filters.geography:
                geography = meta.get("geography")
                if geography is None or geography not in filters.geography:
                    return False
            year = meta.get("year")
            if year is None:
                return keep_unknown_year or (
                    filters.year_from is None and filters.year_to is None
                )
            if filters.year_from is not None and year < filters.year_from:
                return False
            return not (filters.year_to is not None and year > filters.year_to)

        return keeps

    def _apply_source_scope(
        self,
        experiments: list[ExperimentRow],
        filters: AskFilters | None,
        *,
        keep_unknown_year: bool = False,
    ) -> list[ExperimentRow]:
        """Geography / publication-year filters (track: «отечественная vs зарубежная»)."""
        if filters is None or (
            not filters.geography and filters.year_from is None and filters.year_to is None
        ):
            return experiments
        recorder = self.run_recorder
        if recorder is None:
            return experiments
        keeps = self._scope_predicate(
            filters, recorder.source_metadata(), keep_unknown_year=keep_unknown_year
        )
        return [experiment for experiment in experiments if keeps(experiment.source_id)]

    def _effective_filters(self, request: AskRequest) -> AskFilters | None:
        """Explicit filters enriched with the question's own time scope.

        Track example Q3 phrases the range in words («за последние 5 лет») —
        it must act exactly like the UI year filter. Explicit filters win.
        """
        from datetime import date

        year_from, year_to = parse_time_scope(
            request.question, now_year=date.today().year
        )
        if year_from is None and year_to is None:
            return request.filters
        base = request.filters or AskFilters()
        return base.model_copy(
            update={
                "year_from": base.year_from if base.year_from is not None else year_from,
                "year_to": base.year_to if base.year_to is not None else year_to,
            }
        )

    def _apply_scope_to_evidence(
        self,
        evidence: list[EvidenceSpan],
        filters: AskFilters | None,
        *,
        keep_unknown_year: bool = False,
    ) -> list[EvidenceSpan]:
        """The answer packet must honor geography/year scope, not only the
        experiment table — otherwise out-of-range spans leak into synthesis."""
        if filters is None or (
            not filters.geography and filters.year_from is None and filters.year_to is None
        ):
            return evidence
        recorder = self.run_recorder
        if recorder is None:
            return evidence
        keeps = self._scope_predicate(
            filters, recorder.source_metadata(), keep_unknown_year=keep_unknown_year
        )
        return [span for span in evidence if keeps(span.source_id)]

    def _drop_constraint_violating_evidence(
        self,
        question: str,
        evidence: list[EvidenceSpan],
    ) -> list[EvidenceSpan]:
        """Remove evidence whose own table facts VIOLATE a subject-bound
        numeric constraint from the question.

        For «сульфаты … ≤300 мг/л, сухой остаток ≤1000 мг/дм³» a span stating
        «сухой остаток: 1200 мг/л» is dropped, while spans with no relevant
        facts are kept (absence of data is not a violation — honest recall).
        """
        constraints = parse_parameter_constraints(question)
        if not constraints:
            return evidence
        kept: list[EvidenceSpan] = []
        for span in evidence:
            facts: list[tuple[str, float, str]] = []
            for fact in parse_labeled_span_facts(span.visible_text):
                # The constrained subject may be the row subject (tall tables)
                # or the column property (wide tables) — match either.
                facts.append((fact.subject, fact.value, fact.unit))
                if fact.prop and fact.prop != fact.subject:
                    facts.append((fact.prop, fact.value, fact.unit))
            if not facts or facts_satisfy_constraints(facts, constraints):
                kept.append(span)
        # Never blank the packet on constraint filtering alone.
        return kept or evidence

    def _apply_numeric_constraints(
        self,
        question: str,
        experiments: list[ExperimentRow],
    ) -> list[ExperimentRow]:
        """Numeric constraints from the question («≤300 мг/л», «от 100 до 300 мг/л»…).

        Contract (domain.quantities): only unit-bearing constraints filter, and
        units are compared after canonicalization (мг/дм³ ≡ мг/л), so «до 2020
        года» never silently drops valid measurements.
        """
        constraints = parse_numeric_constraints(question)
        if not constraints:
            return experiments
        return [
            experiment
            for experiment in experiments
            if satisfies_constraints(
                experiment.measurement.get("value"),
                experiment.measurement.get("unit"),
                constraints,
            )
        ]

    def _augment_with_retrieval(
        self,
        *,
        request: AskRequest,
        allowed_evidence: list[EvidenceSpan],
        selected_evidence: list[EvidenceSpan],
    ) -> list[EvidenceSpan]:
        if self.retrieval_service is None:
            return selected_evidence
        allowed_by_id = {span.span_id: span for span in allowed_evidence}
        source_ids: list[str] | None = None
        if request.filters:
            # Both filter spellings are honored (audit H9: `source_id` scope
            # silently leaked other sources into the LLM packet).
            scoped = self._list_filter_values(request.filters, "source_ids", "source_id")
            if scoped:
                source_ids = sorted(scoped)
        try:
            retrieved_ids = self.retrieval_service.retrieve_span_ids(
                question=request.question,
                allowed_labels=sorted(self.source_label_policy.allowed_labels),
                source_ids=source_ids,
            )
        except Exception:  # retrieval degradation is silent by contract
            return selected_evidence
        present = {span.span_id for span in selected_evidence}
        extras = [
            allowed_by_id[span_id]
            for span_id in retrieved_ids
            if span_id in allowed_by_id and span_id not in present
        ]
        return selected_evidence + extras

    def _load_packet(self) -> EvidenceLedgerPacket:
        if self.ledger_repository is None:
            # No repository configured: return an empty packet, not synthetic
            # demo data. ask() degrades to an honest low-confidence empty answer.
            return EvidenceLedgerPacket(
                evidence=[],
                measurements=[],
                effects=[],
                experiments=[],
                source_titles={},
                conflicts=[],
                gaps=[],
            )
        # Loading 12k+ spans from DuckDB per question dominated ask latency;
        # the packet is cached and invalidated by the ledger's data version.
        version = getattr(self.ledger_repository, "data_version", None)
        if (
            version is not None
            and self._packet_cache is not None
            and self._packet_cache[0] == version
        ):
            return self._packet_cache[1]
        packet = self.ledger_repository.load_evidence_packet()
        if version is not None:
            self._packet_cache = (version, packet)
        return packet

    def _select_experiments(
        self,
        *,
        question: str,
        experiments: list[ExperimentRow],
        request_filters: AskFilters | None = None,
    ) -> list[ExperimentRow]:
        normalized_question = self._normalize(question)
        requested_property = self._requested_property(question, experiments)
        has_request_filters = self._has_filter_constraints(request_filters)
        requested_material_tokens = self._requested_material_tokens(question)
        known_material_tokens = self._known_material_tokens(experiments)
        matched_tokens = requested_material_tokens.intersection(known_material_tokens)
        # Per-token honesty (audit M17/C4): unknown materials drop out, but a
        # comparison question keeps its known half; all-unknown means an
        # honest empty answer (gaps/follow-ups explain why).
        if requested_material_tokens and not matched_tokens:
            return []
        exact_materials = {
            self._normalize_material_token(experiment.material_name)
            for experiment in experiments
            if self._normalize_material_token(experiment.material_name)
            and self._normalize_material_token(experiment.material_name) in normalized_question
        }
        exact_materials.update(matched_tokens)
        # Question-side alias resolution: «МН30» is the Russian designation of
        # CuNi30 — the entity alias table, not string similarity, decides.
        exact_materials.update(
            self._alias_material_tokens(question).intersection(known_material_tokens)
        )
        filtered_experiments: list[ExperimentRow] = []
        scored: list[tuple[int, ExperimentRow]] = []
        for experiment in experiments:
            if not self._matches_filters(experiment, request_filters):
                continue
            filtered_experiments.append(experiment)
            if (
                exact_materials
                and self._normalize_material_token(experiment.material_name)
                not in exact_materials
            ):
                continue
            if requested_property and not self._property_matches(requested_property, experiment):
                continue
            score = self._score_experiment(question, experiment, requested_property)
            if score > 0:
                scored.append((score, experiment))
        if not scored and not requested_property:
            if exact_materials:
                # A material was explicitly requested and matched — that IS
                # the signal, even when no regime/property keyword scored.
                return [
                    experiment
                    for experiment in filtered_experiments
                    if self._normalize_material_token(experiment.material_name)
                    in exact_materials
                ][:5]
            if has_request_filters:
                # The user scoped explicitly — the scope itself is the query.
                return filtered_experiments[:5]
            # No signal matched: an honest empty beats five arbitrary rows
            # presented as an answer (audit C1).
            return []
        scored.sort(key=lambda item: (-item[0], item[1].experiment_id))
        return [experiment for _, experiment in scored[:5]]

    def _matches_filters(
        self,
        experiment: ExperimentRow,
        filters: AskFilters | None,
    ) -> bool:
        if not filters or self._is_filter_set_empty(filters):
            return True
        source_filter = self._list_filter_values(filters, "source_ids", "source_id")
        if source_filter and not self._matches_source_filter(experiment.source_id, source_filter):
            return False
        material_filter = self._text_filter_values(filters, "material_name", "material")
        if material_filter and not self._matches_text_filter(
            experiment.material_name, material_filter
        ):
            return False
        property_filter = self._text_filter_values(filters, "property_name", "property")
        if property_filter and not self._matches_text_filter(
            experiment.property_name, property_filter
        ):
            return False
        regime_filter = self._text_filter_values(filters, "regime_summary", "regime")
        if regime_filter and not self._matches_text_filter(
            experiment.regime_summary, regime_filter
        ):
            return False
        experiment_filter = self._text_filter_values(filters, "experiment_id")
        if experiment_filter and not self._matches_text_filter(
            experiment.experiment_id, experiment_filter
        ):
            return False
        regime_id_filter = self._text_filter_values(filters, "regime_id")
        if not regime_id_filter:
            return True
        return self._matches_text_filter(experiment.regime_id, regime_id_filter)

    def _matches_source_filter(self, source_id: str | None, allowed_source_ids: set[str]) -> bool:
        if not allowed_source_ids:
            return True
        return source_id is not None and source_id in allowed_source_ids

    def _has_filter_constraints(self, filters: AskFilters | None) -> bool:
        if not filters:
            return False
        return not self._is_filter_set_empty(filters)

    def _is_filter_set_empty(self, filters: AskFilters) -> bool:
        return all(not self._list_filter_values(filters, key) for key in (
            "source_ids",
            "source_id",
            "material_name",
            "material",
            "property_name",
            "property",
            "regime_summary",
            "regime",
            "experiment_id",
            "regime_id",
        ))

    def _list_filter_values(self, filters: AskFilters, *keys: str) -> set[str]:
        for key in keys:
            raw = getattr(filters, key, None)
            if not raw:
                continue
            if isinstance(raw, list):
                return {str(item).strip() for item in raw if str(item).strip()}
        return set()

    def _text_filter_values(self, filters: AskFilters, *keys: str) -> set[str]:
        for key in keys:
            raw = getattr(filters, key, None)
            if not raw:
                continue
            if isinstance(raw, list):
                normalized_values = {
                    self._normalize(str(item).strip())
                    for item in raw
                    if str(item).strip()
                }
                return {value for value in normalized_values if value}
        return set()

    def _matches_text_filter(self, value: str, candidates: set[str]) -> bool:
        if not candidates:
            return True
        normalized_value = self._normalize(value)
        return any(candidate in normalized_value for candidate in candidates)

    def _score_experiment(
        self, question: str, experiment: ExperimentRow, requested_property: str | None
    ) -> int:
        normalized_question = self._normalize(question)
        score = 0
        material = self._normalize_material_token(experiment.material_name)
        if material and material in normalized_question:
            score += 6
        elif self._shared_material_element_count(normalized_question, experiment) >= 2:
            # Same alloy system (e.g. a «Ni-Cu» question vs a Ni-30Cu row) even
            # when the exact alloy code was not spelled out.
            score += 4
        if requested_property and self._property_matches(requested_property, experiment):
            score += 5
        if self._regime_matches(normalized_question, experiment):
            score += 4
        score += self._shared_numeric_bonus(normalized_question, experiment.regime_summary)
        return score

    def _requested_property(
        self, question: str, experiments: list[ExperimentRow] | None = None
    ) -> str | None:
        normalized_question = self._normalize(question)
        # Canonical property families recognised by surface synonyms.
        if "электропровод" in normalized_question or "conductivity" in normalized_question:
            return "conductivity"
        if "vickers" in normalized_question or "виккер" in normalized_question:
            return "vickers_hardness"
        if "rockwell" in normalized_question or "роквел" in normalized_question:
            return "rockwell_hardness"
        if "hardness" in normalized_question or "тверд" in normalized_question:
            return "hardness"
        # Generic: any property actually present in the corpus whose name
        # appears in the question (no domain hardcode beyond the synonyms).
        for experiment in experiments or []:
            property_name = self._normalize(experiment.property_name)
            if property_name and property_name in normalized_question:
                return experiment.property_id.lower()
        return None

    def _property_matches(self, requested_property: str, experiment: ExperimentRow) -> bool:
        property_id = experiment.property_id.lower()
        property_name = experiment.property_name.lower()
        if requested_property == "hardness":
            return "hardness" in property_id or "тверд" in property_name
        if requested_property == "conductivity":
            return "conductivity" in property_id or "электропровод" in property_name
        return requested_property in property_id

    def _regime_matches(self, normalized_question: str, experiment: ExperimentRow) -> bool:
        regime = self._normalize(experiment.regime_summary)
        # Canonical regime families by synonym.
        if ("старен" in normalized_question or "aging" in normalized_question) and (
            "старен" in regime or "aging" in regime
        ):
            return True
        if ("отжиг" in normalized_question or "anneal" in normalized_question) and (
            "отжиг" in regime or "anneal" in regime
        ):
            return True
        # Generic: a specific content word shared between the question and the
        # regime summary (any process, not only aging/annealing).
        return bool(self._shared_content_tokens(normalized_question, regime))

    def _evidence_for_experiments(
        self,
        evidence: list[EvidenceSpan],
        experiments: list[ExperimentRow],
    ) -> list[EvidenceSpan]:
        requested_span_ids = {
            span_id
            for experiment in experiments
            for span_id in experiment.evidence_ids
        }
        return [span for span in evidence if span.span_id in requested_span_ids]

    def _graph_path_for_experiment(
        self,
        experiment: ExperimentRow,
        evidence: list[EvidenceSpan],
    ) -> GraphPath:
        primary_span = next(span for span in evidence if span.span_id in experiment.evidence_ids)
        measurement_id = f"meas:{experiment.experiment_id}:{experiment.property_id}"
        return GraphPath(
            path_id=f"path_{stable_hash([experiment.experiment_id, experiment.property_id], 10)}",
            nodes=[
                experiment.material_id,
                experiment.experiment_id,
                experiment.regime_id,
                f"step_{experiment.regime_id}",
                measurement_id,
                experiment.property_id,
                primary_span.span_id,
                primary_span.source_id,
            ],
            relationships=[
                "USED_IN_EXPERIMENT",
                "APPLIES_REGIME",
                "HAS_STEP",
                "HAS_MEASUREMENT",
                "OF_PROPERTY",
                "SUPPORTED_BY",
                "FROM_DOCUMENT",
            ],
        )

    def _answer_sentence_for_experiment(
        self,
        experiment: ExperimentRow,
        graph_path: GraphPath,
    ) -> AnswerSentence:
        value = experiment.measurement.get("value")
        unit = experiment.measurement.get("unit")
        delta = experiment.measurement.get("delta_value")
        delta_unit = experiment.measurement.get("delta_unit")
        direction = experiment.measurement.get("effect_direction")
        value_text = self._format_value(value, unit)
        delta_text = "" if delta is None else f", Δ {self._format_value(delta, delta_unit)}"
        sentence = (
            f"{experiment.material_name}: {experiment.regime_summary} дал эффект "
            f"{direction} по свойству {experiment.property_name}: {value_text}{delta_text}."
        )
        return AnswerSentence(
            sentence=sentence,
            supporting_span_ids=experiment.evidence_ids,
            supporting_fact_ids=[f"fact:{experiment.experiment_id}:{experiment.property_id}"],
            graph_path_ids=[graph_path.path_id],
        )

    def _source_context(
        self,
        packet: EvidenceLedgerPacket,
        selected_evidence: list[EvidenceSpan],
    ) -> dict[str, str]:
        """source_id -> «Title, 2019, ru» labels for literature-review grouping."""
        metadata: dict[str, dict[str, Any]] = {}
        if self.run_recorder is not None:
            with contextlib.suppress(Exception):
                metadata = self.run_recorder.source_metadata()
        context: dict[str, str] = {}
        for span in selected_evidence:
            if span.source_id in context:
                continue
            parts = [packet.source_titles.get(span.source_id, "")[:80]]
            meta = metadata.get(span.source_id, {})
            if meta.get("year"):
                parts.append(str(meta["year"]))
            if meta.get("geography"):
                parts.append(str(meta["geography"]))
            label = ", ".join(part for part in parts if part)
            if label:
                context[span.source_id] = label
        return context

    def _confidence_level(
        self,
        question: str,
        selected_experiments: list[ExperimentRow],
        summary: list[AnswerSentence],
        selected_evidence: list[EvidenceSpan],
    ) -> Literal["low", "medium", "high"]:
        """Honest confidence levels.

        high — the question's material/property signal matched structured
        experiments; medium — a verified evidence-grounded answer without a
        structured match (the normal case on the real corpus); low — nothing
        found (audit C1: the old binary «high if non-empty» presented
        arbitrary rows as trustworthy).
        """
        if selected_experiments:
            requested_tokens = self._requested_material_tokens(question)
            matched_material = requested_tokens.intersection(
                self._known_material_tokens(selected_experiments)
            )
            if matched_material or self._requested_property(question, selected_experiments):
                return "high"
            return "medium"
        if summary and selected_evidence:
            return "medium"
        return "low"

    def _conflicts_for_question(
        self,
        question: str,
        conflicts: list[dict[str, object]],
        selected_experiments: list[ExperimentRow],
    ) -> list[dict[str, object]]:
        normalized_question = self._normalize(question)
        if "противор" in normalized_question or "conflict" in normalized_question:
            return conflicts
        if "method" in normalized_question or "метод" in normalized_question:
            return conflicts
        # Relevance gate (audit M1): a conflict is attached only when it
        # shares a material/experiment/span with the selected evidence.
        selected_material_ids = {e.material_id for e in selected_experiments}
        selected_experiment_ids = {e.experiment_id for e in selected_experiments}
        selected_span_ids = {
            span_id for e in selected_experiments for span_id in e.evidence_ids
        }

        def relevant(conflict: dict[str, object]) -> bool:
            if str(conflict.get("material_id") or "") in selected_material_ids:
                return True
            experiment_ids = conflict.get("experiment_ids")
            if isinstance(experiment_ids, list) and set(
                str(item) for item in experiment_ids
            ) & selected_experiment_ids:
                return True
            span_ids = conflict.get("supporting_span_ids")
            return isinstance(span_ids, list) and bool(
                set(str(item) for item in span_ids) & selected_span_ids
            )

        return [conflict for conflict in conflicts if relevant(conflict)]

    def _gaps_for_question(
        self,
        *,
        question: str,
        packet_gaps: list[dict[str, object]],
        selected_experiments: list[ExperimentRow],
        unmatched_material_tokens: set[str],
    ) -> list[dict[str, object]]:
        if unmatched_material_tokens:
            return []
        requested_property = self._requested_property(question, selected_experiments)
        if not selected_experiments or requested_property == "conductivity":
            return packet_gaps
        return []

    def _follow_up_queries(
        self,
        *,
        question: str,
        experiments: list[ExperimentRow],
        unmatched_material_tokens: set[str],
    ) -> list[str]:
        if unmatched_material_tokens:
            return [
                f"Что было с {material_name}?"
                for material_name in self._closest_material_names(
                    requested_tokens=unmatched_material_tokens,
                    experiments=experiments,
                )
            ]
        return self._corpus_follow_ups(question, experiments)

    def _normalize(self, value: str) -> str:
        return value.lower().replace("ё", "е").replace("-", "")

    def _normalize_material_token(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower().replace("ё", "е"))

    def _requested_material_tokens(self, question: str) -> set[str]:
        compact_question = re.sub(r"[-_/]+", "", question.lower())
        tokens = {
            self._normalize_material_token(match.group(0))
            for match in MATERIAL_TOKEN_RE.finditer(compact_question)
        }
        tokens.update(
            self._normalize_material_token(match.group(0))
            for match in MATERIAL_SPACED_TOKEN_RE.finditer(question.lower())
            if self._is_plausible_spaced_material_token(match.group(0))
        )
        return {
            token
            for token in tokens
            if _ALLOY_TOKEN_RE.fullmatch(token) and token not in _CHEMICAL_FORMULA_VETO
        }

    def _is_plausible_spaced_material_token(self, token: str) -> bool:
        numbers = [int(value) for value in re.findall(r"\d{1,3}", token)]
        return bool(numbers) and all(value <= 100 for value in numbers)

    _ALIAS_CANDIDATE_RE = re.compile(r"\b[a-zа-яё]{1,8}\d{1,3}[a-zа-яё0-9]*\b", re.IGNORECASE)

    def _alias_material_tokens(self, question: str) -> set[str]:
        """Material tokens resolved through the entity alias table (RU codes)."""
        repository = self.ledger_repository
        find_entity = getattr(repository, "find_entity", None)
        if find_entity is None:
            return set()
        tokens: set[str] = set()
        for match in self._ALIAS_CANDIDATE_RE.finditer(question.lower()):
            candidate = match.group(0)
            try:
                entity = find_entity(candidate, "material")
            except Exception:  # alias lookup is additive, never breaks answers
                continue
            if entity is not None:
                tokens.add(self._normalize_material_token(str(entity["canonical_name"])))
        return {token for token in tokens if token}

    def _known_material_tokens(self, experiments: list[ExperimentRow]) -> set[str]:
        return {
            self._normalize_material_token(experiment.material_name)
            for experiment in experiments
            if self._normalize_material_token(experiment.material_name)
        }

    def _unmatched_material_tokens(
        self,
        *,
        question: str,
        experiments: list[ExperimentRow],
    ) -> set[str]:
        requested_tokens = self._requested_material_tokens(question)
        if not requested_tokens:
            return set()
        known_tokens = self._known_material_tokens(experiments)
        return requested_tokens.difference(known_tokens)

    def _closest_material_names(
        self,
        *,
        requested_tokens: set[str],
        experiments: list[ExperimentRow],
    ) -> list[str]:
        material_names = sorted({experiment.material_name for experiment in experiments})
        scored: list[tuple[float, str]] = []
        for material_name in material_names:
            material_token = self._normalize_material_token(material_name)
            best_score = max(
                SequenceMatcher(None, requested_token, material_token).ratio()
                for requested_token in requested_tokens
            )
            if best_score >= 0.45:
                scored.append((best_score, material_name))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [material_name for _, material_name in scored[:3]]

    def _format_value(self, value: object, unit: object) -> str:
        value_text = f"{value:g}" if isinstance(value, int | float) else str(value)
        return f"{value_text} {unit}".strip()

    _NUMERIC_TOKEN_RE = re.compile(r"\d+")
    _CONTENT_TOKEN_RE = re.compile(r"[a-zа-я]{5,}")

    def _shared_material_element_count(
        self, normalized_question: str, experiment: ExperimentRow
    ) -> int:
        """How many alloy elements the question and the material share.

        Generic replacement for the old Ni-Cu-family literals: two shared
        elements mark the same alloy system for any material in the ontology.
        """
        material = self._normalize_material_token(experiment.material_name)
        material_elements = {element for element in MATERIAL_ELEMENTS if element in material}
        question_elements = {
            element for element in MATERIAL_ELEMENTS if element in normalized_question
        }
        return len(material_elements & question_elements)

    def _shared_numeric_bonus(self, normalized_question: str, regime_summary: str) -> int:
        """Bonus for regime numbers (temperature, duration, …) the question
        repeats — corpus-generic, replacing the literal 700/8 checks."""
        regime = self._normalize(regime_summary)
        question_numbers = set(self._NUMERIC_TOKEN_RE.findall(normalized_question))
        regime_numbers = set(self._NUMERIC_TOKEN_RE.findall(regime))
        return min(len(question_numbers & regime_numbers), 2)

    def _shared_content_tokens(self, normalized_question: str, normalized_text: str) -> set[str]:
        question_tokens = set(self._CONTENT_TOKEN_RE.findall(normalized_question))
        text_tokens = set(self._CONTENT_TOKEN_RE.findall(normalized_text))
        return question_tokens & text_tokens

    def _corpus_follow_ups(self, question: str, experiments: list[ExperimentRow]) -> list[str]:
        """Follow-ups derived from corpus materials not named in the question
        (replaces the hardcoded Ni-Cu follow-up templates)."""
        normalized_question = self._normalize(question)
        suggestions: list[str] = []
        for material in sorted({experiment.material_name.strip() for experiment in experiments}):
            if not material:
                continue
            token = self._normalize_material_token(material)
            if token and token not in normalized_question:
                suggestions.append(f"Что было с {material}?")
            if len(suggestions) >= 2:
                break
        return suggestions
