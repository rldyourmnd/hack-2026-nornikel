import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { QuestionForm } from "@/features/ask-question";
import {
  askQuestion,
  listSources,
  type AskFilters,
  type AskResponse,
  type SourceSummary,
} from "@/shared/api";
import { defaultQuestion } from "@/shared/i18n/ru";
import { Panel } from "@/shared/ui";
import { EvidenceList } from "@/widgets/artifact-bank";
import { EvaluationDashboard } from "@/widgets/evaluation-dashboard";
import { GraphView } from "@/widgets/graph-view";

type AnalysisWorkbenchProps = {
  // A question injected from another page (e.g. a gap cell in Analytics).
  injectedQuestion?: string | null;
};

export function AnalysisWorkbench({ injectedQuestion }: AnalysisWorkbenchProps) {
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState(defaultQuestion);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  const [materialFilter, setMaterialFilter] = useState("");
  const [propertyFilter, setPropertyFilter] = useState("");
  const [regimeFilter, setRegimeFilter] = useState("");
  const [experimentFilter, setExperimentFilter] = useState("");
  const [regimeIdFilter, setRegimeIdFilter] = useState("");
  const [geographyFilter, setGeographyFilter] = useState("");
  const [yearFromFilter, setYearFromFilter] = useState("");
  const [yearToFilter, setYearToFilter] = useState("");

  useEffect(() => {
    void refreshSources();
  }, []);

  // Enrichment runs in the background: while any source is still «обработка»,
  // keep polling so the card flips to «готов» without a manual refresh.
  useEffect(() => {
    if (!sources.some((source) => source.status === "running")) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshSources();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [sources]);

  async function refreshSources() {
    try {
      setArtifactError(null);
      setSources(await listSources());
    } catch (err) {
      setArtifactError(err instanceof Error ? err.message : "Не удалось загрузить источники");
    }
  }

  useEffect(() => {
    setSelectedSourceIds((previous) => {
      const availableIds = new Set(sources.map((source) => source.source_id));
      const next = new Set(
        [...previous].filter((sourceId) => availableIds.has(sourceId)),
      );
      if (next.size !== previous.size) {
        return next;
      }
      return previous;
    });
  }, [sources]);

  function splitFilterList(raw: string): string[] {
    return raw
      .split(/[\n,]/)
      .map((value) => value.trim())
      .filter((value) => value.length > 0);
  }

  function buildFilters(): AskFilters {
    const filters: AskFilters = {};

    if (selectedSourceIds.size > 0) {
      filters.source_ids = [...selectedSourceIds];
    }

    const materials = splitFilterList(materialFilter);
    if (materials.length > 0) {
      filters.material = materials;
    }

    const properties = splitFilterList(propertyFilter);
    if (properties.length > 0) {
      filters.property = properties;
    }

    const regimes = splitFilterList(regimeFilter);
    if (regimes.length > 0) {
      filters.regime = regimes;
    }

    const experiments = splitFilterList(experimentFilter);
    if (experiments.length > 0) {
      filters.experiment_id = experiments;
    }

    const regimeIds = splitFilterList(regimeIdFilter);
    if (regimeIds.length > 0) {
      filters.regime_id = regimeIds;
    }

    if (geographyFilter) {
      filters.geography = [geographyFilter];
    }
    const yearFrom = Number.parseInt(yearFromFilter, 10);
    if (!Number.isNaN(yearFrom)) {
      filters.year_from = yearFrom;
    }
    const yearTo = Number.parseInt(yearToFilter, 10);
    if (!Number.isNaN(yearTo)) {
      filters.year_to = yearTo;
    }

    return filters;
  }

  async function handleSubmit(nextQuestion: string) {
    setLoading(true);
    setError(null);
    try {
      setQuestion(nextQuestion);
      setAnswer(await askQuestion(nextQuestion, buildFilters()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить запрос");
    } finally {
      setLoading(false);
    }
  }

  // A gap cell clicked on the Analytics page lands here as a ready question.
  useEffect(() => {
    if (injectedQuestion) {
      setQuestion(injectedQuestion);
      void handleSubmit(injectedQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [injectedQuestion]);

  function clearFilters() {
    setSelectedSourceIds(new Set());
    setMaterialFilter("");
    setPropertyFilter("");
    setRegimeFilter("");
    setExperimentFilter("");
    setRegimeIdFilter("");
    setGeographyFilter("");
    setYearFromFilter("");
    setYearToFilter("");
  }

  const isFilterActive =
    selectedSourceIds.size > 0 ||
    materialFilter.trim().length > 0 ||
    propertyFilter.trim().length > 0 ||
    regimeFilter.trim().length > 0 ||
    experimentFilter.trim().length > 0 ||
    regimeIdFilter.trim().length > 0 ||
    geographyFilter.length > 0 ||
    yearFromFilter.trim().length > 0 ||
    yearToFilter.trim().length > 0;

  return (
    <div className="workbench-grid">
      <div className="stack">
        <Panel title="Вопрос исследователя">
          <div className="qa-filters">
            <div className="filter-group">
              <label>Фильтр по источникам</label>
              <div className="filter-source-list">
                {sources.map((source) => {
                  const checked = selectedSourceIds.has(source.source_id);
                  return (
                    <label className="filter-source-item" key={source.source_id}>
                      <input
                        checked={checked}
                        onChange={(event) => {
                          const next = new Set(selectedSourceIds);
                          if (event.target.checked) {
                            next.add(source.source_id);
                          } else {
                            next.delete(source.source_id);
                          }
                          setSelectedSourceIds(next);
                        }}
                        type="checkbox"
                      />
                      <span>{source.title}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="filter-grid">
              <label className="filter-text-field">
                <span>material / material_name</span>
                <input
                  onChange={(event) => setMaterialFilter(event.target.value)}
                  placeholder="Ni-30Cu, CuNi30"
                  type="text"
                  value={materialFilter}
                />
              </label>
              <label className="filter-text-field">
                <span>property / property_name</span>
                <input
                  onChange={(event) => setPropertyFilter(event.target.value)}
                  placeholder="Vickers hardness, Hardness"
                  type="text"
                  value={propertyFilter}
                />
              </label>
              <label className="filter-text-field">
                <span>regime / regime_summary</span>
                <input
                  onChange={(event) => setRegimeFilter(event.target.value)}
                  placeholder="aging 700 C, anneal"
                  type="text"
                  value={regimeFilter}
                />
              </label>
              <label className="filter-text-field">
                <span>experiment_id</span>
                <input
                  onChange={(event) => setExperimentFilter(event.target.value)}
                  placeholder="exp_nicu_aging_700c_8h"
                  type="text"
                  value={experimentFilter}
                />
              </label>
              <label className="filter-text-field">
                <span>regime_id</span>
                <input
                  onChange={(event) => setRegimeIdFilter(event.target.value)}
                  placeholder="reg_aging_700c_8h_air"
                  type="text"
                  value={regimeIdFilter}
                />
              </label>
              <label className="filter-text-field">
                <span>география</span>
                <select
                  className="gaps-select"
                  onChange={(event) => setGeographyFilter(event.target.value)}
                  value={geographyFilter}
                >
                  <option value="">любая</option>
                  <option value="ru">отечественная</option>
                  <option value="foreign">зарубежная</option>
                </select>
              </label>
              <label className="filter-text-field">
                <span>год от / до</span>
                <div className="year-range">
                  <input
                    onChange={(event) => setYearFromFilter(event.target.value)}
                    placeholder="2015"
                    type="number"
                    value={yearFromFilter}
                  />
                  <input
                    onChange={(event) => setYearToFilter(event.target.value)}
                    placeholder="2026"
                    type="number"
                    value={yearToFilter}
                  />
                </div>
              </label>
            </div>

            <div className="button-row">
              <button
                className="secondary-button"
                disabled={loading || !isFilterActive}
                onClick={clearFilters}
                type="button"
              >
                Сбросить фильтры
              </button>
            </div>
          </div>
          <QuestionForm
            disabled={loading}
            onQuestionChange={setQuestion}
            onSubmit={handleSubmit}
            question={question}
          />
        </Panel>

        <Panel title="Сводка по доказательствам">
          {loading ? (
            <div className="status-pill">
              <Loader2 size={16} />
              Выполняю retrieval и проверку claims
            </div>
          ) : null}
          {error ? (
            <div className="status-pill">
              <AlertTriangle size={16} />
              {error}
            </div>
          ) : null}
          {answer ? (
            <div className="answer-list">
              <div className="status-pill">
                <CheckCircle2 size={16} />
                {"Уверенность: "}
                {answer.confidence === "high"
                  ? "высокая"
                  : answer.confidence === "medium"
                    ? "средняя"
                    : "низкая"}
              </div>
              {answer.answer_summary.length > 0 ? (
                answer.answer_summary.map((sentence) => (
                  <div className="answer-sentence" key={sentence.sentence}>
                    {sentence.sentence}
                  </div>
                ))
              ) : (
                <div className="answer-sentence answer-sentence-muted">
                  {answer.gaps.length > 0
                    ? "В выбранном корпусе нет измерения для запрошенного свойства."
                    : "Точного совпадения по введенному материалу и условиям не найдено."}
                </div>
              )}
              {answer.follow_up_queries.length > 0 ? (
                <div className="follow-up-list">
                  {answer.follow_up_queries.map((followUpQuery) => (
                    <button
                      className="secondary-button"
                      disabled={loading}
                      key={followUpQuery}
                      onClick={() => {
                        void handleSubmit(followUpQuery);
                      }}
                      type="button"
                    >
                      {followUpQuery}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="status-pill">
              <CheckCircle2 size={16} />
              Готово к первому запросу
            </div>
          )}
        </Panel>

        {answer && answer.conflicts.length > 0 ? (
          <Panel title="Противоречия в данных">
            <div className="answer-list">
              {answer.conflicts.map((conflict, index) => (
                <div
                  className="answer-sentence"
                  key={String(conflict.conflict_group_id ?? index)}
                >
                  <AlertTriangle size={14} />{" "}
                  {String(conflict.summary ?? conflict.type ?? "Конфликт данных")}
                </div>
              ))}
            </div>
          </Panel>
        ) : null}

        {answer && answer.experiments.length > 0 ? (
          <Panel title="Таблица экспериментов">
            <table className="experiment-table">
              <thead>
                <tr>
                  <th>Материал</th>
                  <th>Режим</th>
                  <th>Свойство</th>
                  <th>Эффект</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {answer.experiments.map((experiment) => (
                  <tr key={experiment.experiment_id}>
                    <td>{experiment.material_name}</td>
                    <td>{experiment.regime_summary}</td>
                    <td>{experiment.property_name}</td>
                    <td>
                      {experiment.measurement.effect_direction != null
                        ? String(experiment.measurement.effect_direction)
                        : "—"}
                      {experiment.measurement.value != null
                        ? ` · ${String(experiment.measurement.value)} ${String(
                            experiment.measurement.unit ?? "",
                          )}`
                        : ""}
                    </td>
                    <td>{experiment.evidence_ids.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        ) : null}
      </div>

      <div className="stack">
        {artifactError ? <div className="inline-error">{artifactError}</div> : null}
        {answer ? (
          <>
            {answer.evidence.length > 0 ? <EvidenceList evidence={answer.evidence} /> : null}
            {answer.graph_paths.length > 0 ? <GraphView graphPaths={answer.graph_paths} /> : null}
            <EvaluationDashboard answer={answer} />
          </>
        ) : (
          <Panel title="Рабочая область">
            <p className="page-caption">
              Первый запрос покажет таблицу экспериментов, evidence cards, графовый путь,
              противоречия и проверку каждого предложения. Загрузка документов — в разделе
              «Данные», интерактивный граф — в разделе «Граф знаний».
            </p>
          </Panel>
        )}
      </div>
    </div>
  );
}
