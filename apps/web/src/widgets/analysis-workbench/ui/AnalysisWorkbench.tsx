import {
  AlertTriangle,
  CheckCircle2,
  FileSearch,
  Loader2,
  MessagesSquare,
  Network,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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

const LOADING_STEPS = [
  "Сканирую полнотекстовый индекс и BM25",
  "Ранжирую dense-векторы evidence spans",
  "Собираю пакет источников и графовые связи",
  "Синтезирую ответ и проверяю claims",
  "Подсвечиваю цитаты и источники",
];

const SOURCE_COLORS = [
  "#2563eb",
  "#0d9488",
  "#7c3aed",
  "#d97706",
  "#0891b2",
  "#059669",
  "#dc2626",
  "#475569",
];

function splitFilterList(raw: string): string[] {
  return raw
    .split(/[\n,]/)
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

export function AnalysisWorkbench({ injectedQuestion }: AnalysisWorkbenchProps) {
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState(defaultQuestion);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [externalMode, setExternalMode] = useState(true);
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
  const [highlightedSpanId, setHighlightedSpanId] = useState<string | null>(null);

  const citationIndex = useMemo(() => {
    const index = new Map<string, number>();
    answer?.evidence.forEach((span, spanIndex) => {
      index.set(span.span_id, spanIndex + 1);
    });
    return index;
  }, [answer]);

  const sourceColorMap = useMemo(() => {
    const map = new Map<string, string>();
    answer?.evidence.forEach((span) => {
      if (!map.has(span.source_id)) {
        map.set(span.source_id, SOURCE_COLORS[map.size % SOURCE_COLORS.length]);
      }
    });
    return map;
  }, [answer]);

  const spanColorMap = useMemo(() => {
    const map = new Map<string, string>();
    answer?.evidence.forEach((span) => {
      map.set(span.span_id, sourceColorMap.get(span.source_id) ?? SOURCE_COLORS[0]);
    });
    return map;
  }, [answer, sourceColorMap]);

  const activeSource = sources.length > 0 ? sources[loadingStep % Math.min(sources.length, 12)] : null;

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0);
      return;
    }
    const timer = window.setInterval(() => {
      setLoadingStep((step) => step + 1);
    }, 950);
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    void refreshSources();
  }, []);

  useEffect(() => {
    if (!sources.some((source) => source.status === "running")) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshSources();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [sources]);

  useEffect(() => {
    setSelectedSourceIds((previous) => {
      const availableIds = new Set(sources.map((source) => source.source_id));
      const next = new Set([...previous].filter((sourceId) => availableIds.has(sourceId)));
      return next.size !== previous.size ? next : previous;
    });
  }, [sources]);

  useEffect(() => {
    if (injectedQuestion) {
      setQuestion(injectedQuestion);
      void handleSubmit(injectedQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [injectedQuestion]);

  async function refreshSources() {
    try {
      setArtifactError(null);
      setSources(await listSources());
    } catch (err) {
      setArtifactError(err instanceof Error ? err.message : "Не удалось загрузить источники");
    }
  }

  function buildFilters(): AskFilters {
    const filters: AskFilters = {};
    if (selectedSourceIds.size > 0) filters.source_ids = [...selectedSourceIds];

    const materials = splitFilterList(materialFilter);
    if (materials.length > 0) filters.material = materials;
    const properties = splitFilterList(propertyFilter);
    if (properties.length > 0) filters.property = properties;
    const regimes = splitFilterList(regimeFilter);
    if (regimes.length > 0) filters.regime = regimes;
    const experiments = splitFilterList(experimentFilter);
    if (experiments.length > 0) filters.experiment_id = experiments;
    const regimeIds = splitFilterList(regimeIdFilter);
    if (regimeIds.length > 0) filters.regime_id = regimeIds;
    if (geographyFilter) filters.geography = [geographyFilter];

    const yearFrom = Number.parseInt(yearFromFilter, 10);
    if (!Number.isNaN(yearFrom)) filters.year_from = yearFrom;
    const yearTo = Number.parseInt(yearToFilter, 10);
    if (!Number.isNaN(yearTo)) filters.year_to = yearTo;
    return filters;
  }

  async function handleSubmit(nextQuestion: string) {
    setLoading(true);
    setError(null);
    setHighlightedSpanId(null);
    try {
      setQuestion(nextQuestion);
      const allowedLabels = externalMode ? ["public", "internal"] : undefined;
      setAnswer(await askQuestion(nextQuestion, buildFilters(), allowedLabels));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить запрос");
    } finally {
      setLoading(false);
    }
  }

  function focusEvidence(spanId: string) {
    setHighlightedSpanId(spanId);
    document.getElementById(`evidence-${spanId}`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }

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

  const verification = answer?.verification;

  return (
    <div className="workbench-grid qa-workbench">
      <div className="stack">
        <Panel title="Чат с графом знаний">
          <div className="qa-console-head">
            <div className="qa-console-icon">
              <MessagesSquare size={22} />
            </div>
            <div>
              <div className="qa-console-title">Jury-ready question</div>
              <p>
                Тестовый вопрос уже подставлен из списка жюри. Ответ строится по full graph,
                затем каждое предложение связывается с evidence cards.
              </p>
            </div>
          </div>

          <button
            className="sample-question-card"
            disabled={loading}
            onClick={() => setQuestion(defaultQuestion)}
            type="button"
          >
            <Sparkles size={17} />
            <span>{defaultQuestion}</span>
          </button>

          <QuestionForm
            disabled={loading}
            onQuestionChange={setQuestion}
            onSubmit={handleSubmit}
            question={question}
          />

          <label className="mode-toggle mode-toggle-card">
            <input
              checked={externalMode}
              onChange={(event) => setExternalMode(event.target.checked)}
              type="checkbox"
            />
            <span>
              Режим жюри: видны источники <b>public</b> + <b>internal</b>; служебные метки не
              попадают в ответ.
            </span>
          </label>

          <details className="filters-details">
            <summary>Сузить область поиска: источник, материал, условия, география, годы</summary>
            <div className="qa-filters">
              <div className="filter-group">
                <label>Фильтр по источникам</label>
                <div className="filter-source-list">
                  {sources.slice(0, 60).map((source) => {
                    const checked = selectedSourceIds.has(source.source_id);
                    return (
                      <label className="filter-source-item" key={source.source_id}>
                        <input
                          checked={checked}
                          onChange={(event) => {
                            const next = new Set(selectedSourceIds);
                            if (event.target.checked) next.add(source.source_id);
                            else next.delete(source.source_id);
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
                    placeholder="шахтная вода, никель, католит"
                    type="text"
                    value={materialFilter}
                  />
                </label>
                <label className="filter-text-field">
                  <span>property / property_name</span>
                  <input
                    onChange={(event) => setPropertyFilter(event.target.value)}
                    placeholder="сульфаты, SO2, скорость потока"
                    type="text"
                    value={propertyFilter}
                  />
                </label>
                <label className="filter-text-field">
                  <span>regime / regime_summary</span>
                  <input
                    onChange={(event) => setRegimeFilter(event.target.value)}
                    placeholder="очистка, электролиз, закачка"
                    type="text"
                    value={regimeFilter}
                  />
                </label>
                <label className="filter-text-field">
                  <span>experiment_id</span>
                  <input
                    onChange={(event) => setExperimentFilter(event.target.value)}
                    placeholder="exp_..."
                    type="text"
                    value={experimentFilter}
                  />
                </label>
                <label className="filter-text-field">
                  <span>regime_id</span>
                  <input
                    onChange={(event) => setRegimeIdFilter(event.target.value)}
                    placeholder="regime_..."
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
          </details>
        </Panel>

        <Panel title="Ответ и проверка">
          {loading ? (
            <div className="retrieval-loader" aria-live="polite">
              <div className="retrieval-loader-top">
                <Loader2 size={20} />
                <div>
                  <strong>{LOADING_STEPS[loadingStep % LOADING_STEPS.length]}</strong>
                  <span>
                    {activeSource
                      ? `Сейчас проверяю: ${activeSource.title}`
                      : "Ищу релевантные источники в корпусе"}
                  </span>
                </div>
              </div>
              <div className="retrieval-progress-bar">
                <span style={{ width: `${20 + (loadingStep % LOADING_STEPS.length) * 18}%` }} />
              </div>
            </div>
          ) : null}

          {error ? (
            <div className="status-pill status-pill-danger">
              <AlertTriangle size={16} />
              {error}
            </div>
          ) : null}

          {answer ? (
            <div className="answer-list answer-list-v2">
              <div className="answer-verdict-strip">
                <span>
                  <CheckCircle2 size={16} />
                  Уверенность:{" "}
                  {answer.confidence === "high"
                    ? "высокая"
                    : answer.confidence === "medium"
                      ? "средняя"
                      : "низкая"}
                </span>
                <span>
                  <ShieldCheck size={16} />
                  Citation coverage: {Math.round(answer.verification.citation_coverage * 100)}%
                </span>
                <span>Evidence: {answer.evidence.length}</span>
              </div>

              {answer.answer_summary.length > 0 ? (
                answer.answer_summary.map((sentence, index) => {
                  const citedSpanIds = sentence.supporting_span_ids.filter((spanId) =>
                    citationIndex.has(spanId),
                  );
                  return (
                    <article className="answer-sentence answer-bubble" key={`${sentence.sentence}-${index}`}>
                      <span>{sentence.sentence}</span>
                      <span className="citation-row">
                        {citedSpanIds.map((spanId) => {
                          const color = spanColorMap.get(spanId) ?? SOURCE_COLORS[0];
                          return (
                            <button
                              className="citation-chip citation-chip-source"
                              key={spanId}
                              onClick={() => focusEvidence(spanId)}
                              style={{ borderColor: color, color }}
                              title={`Показать доказательство ${spanId}`}
                              type="button"
                            >
                              {citationIndex.get(spanId)}
                            </button>
                          );
                        })}
                        <span className="citation-verified" title="Подтверждено доказательствами">
                          <CheckCircle2 size={12} /> проверено
                        </span>
                      </span>
                    </article>
                  );
                })
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
                      onClick={() => void handleSubmit(followUpQuery)}
                      type="button"
                    >
                      {followUpQuery}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="qa-empty-state">
              <FileSearch size={34} />
              <strong>Готово к запросу жюри</strong>
              <span>После запуска здесь появится ответ, цветные ссылки на источники и QA-метрики.</span>
            </div>
          )}
        </Panel>

        {answer && answer.conflicts.length > 0 ? (
          <Panel title="Противоречия в данных">
            <div className="answer-list">
              {answer.conflicts.map((conflict, index) => (
                <div className="answer-sentence" key={String(conflict.conflict_group_id ?? index)}>
                  <AlertTriangle size={14} /> {String(conflict.summary ?? conflict.type ?? "Конфликт данных")}
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
                        ? ` · ${String(experiment.measurement.value)} ${String(experiment.measurement.unit ?? "")}`
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

      <div className="stack evidence-rail">
        {artifactError ? <div className="inline-error">{artifactError}</div> : null}
        {answer ? (
          <>
            {answer.evidence.length > 0 ? (
              <EvidenceList
                citationIndex={citationIndex}
                evidence={answer.evidence}
                highlightedSpanId={highlightedSpanId}
                sourceColorMap={sourceColorMap}
              />
            ) : null}
            {answer.graph_paths.length > 0 ? <GraphView graphPaths={answer.graph_paths} /> : null}
            <EvaluationDashboard answer={answer} />
          </>
        ) : (
          <Panel title="Как будет выглядеть результат">
            <div className="qa-result-preview">
              <div>
                <Network size={18} />
                <span>Графовый путь между сущностями</span>
              </div>
              <div>
                <ShieldCheck size={18} />
                <span>Метрики: coverage, unsupported, numeric mismatch</span>
              </div>
              <div>
                <FileSearch size={18} />
                <span>Evidence cards с подсветкой по источникам</span>
              </div>
            </div>
          </Panel>
        )}
        {verification ? (
          <Panel title="Контроль качества ответа">
            <div className="quality-mini-grid">
              <div>
                <b>{Math.round(verification.citation_coverage * 100)}%</b>
                <span>цитируемость</span>
              </div>
              <div>
                <b>{verification.unsupported_claim_count}</b>
                <span>без источника</span>
              </div>
              <div>
                <b>{verification.numeric_mismatch_count}</b>
                <span>числовые ошибки</span>
              </div>
              <div>
                <b>{verification.source_label_leak_count}</b>
                <span>утечки меток</span>
              </div>
            </div>
          </Panel>
        ) : null}
      </div>
    </div>
  );
}
