import type { CSSProperties, ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Circle,
  Clock3,
  Database,
  FileArchive,
  FileSearch,
  FileText,
  Filter,
  Globe2,
  Loader2,
  MapPinned,
  MessagesSquare,
  Network,
  PanelRightOpen,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Table2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  askQuestion,
  fetchSourceEvidence,
  listSources,
  type AskFilters,
  type AskResponse,
  type EvidenceSpan,
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

type SecurityLabel = "public" | "internal" | "confidential" | "restricted";

type SourceGroup = {
  sourceId: string;
  source?: SourceSummary;
  spanIds: string[];
  pages: Set<number>;
};

const JURY_QUESTIONS = [
  {
    label: "Обессоливание воды",
    question:
      "Какие методы обессоливания воды подходят для обогатительной фабрики, если исходная вода содержит сульфаты, хлориды, Ca, Mg, Na по 200-300 мг/л, а требуемый сухой остаток - не более 1000 мг/дм3?",
  },
  {
    label: "Циркуляция католита",
    question:
      "Какие технические решения организации циркуляции католита при электроэкстракции никеля описаны в мировой практике, и какая скорость потока считается оптимальной?",
  },
  {
    label: "Au, Ag и МПГ",
    question:
      "Покажите все эксперименты и публикации по распределению Au, Ag и МПГ между медным и никелевым штейном и шлаком за последние 5 лет.",
  },
  {
    label: "Шахтные воды",
    question: defaultQuestion,
  },
];

const PIPELINE_STEPS = [
  {
    title: "Фиксирую область поиска",
    detail: "вопрос, метки доступа, источники, годы и география",
  },
  {
    title: "Ищу evidence spans",
    detail: "Qdrant hybrid search + DuckDB rejoin, без доверия к индексу",
  },
  {
    title: "Собираю контекст",
    detail: "источники, страницы, таблицы, графовые связи и ограничения",
  },
  {
    title: "Генерирую ответ",
    detail: "каждое предложение должно сослаться на span_id",
  },
  {
    title: "Проверяю claims",
    detail: "citation coverage, числа, метки доступа, unsupported claims",
  },
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
  "#9333ea",
  "#0f766e",
];

const SECURITY_LABELS: Array<{ value: SecurityLabel; label: string; hint: string }> = [
  { value: "public", label: "public", hint: "открытые источники" },
  { value: "internal", label: "internal", hint: "внутренний контур жюри" },
  { value: "confidential", label: "confidential", hint: "закрытые материалы" },
  { value: "restricted", label: "restricted", hint: "ограниченный доступ" },
];

const GEOGRAPHY_LABELS: Record<string, string> = {
  ru: "Россия / отечественная практика",
  foreign: "Зарубежная практика",
  cn: "Китай",
  us: "США",
  usa: "США",
  ca: "Канада",
  fi: "Финляндия",
  de: "Германия",
  au: "Австралия",
  za: "ЮАР",
  kz: "Казахстан",
};

function splitFilterList(raw: string): string[] {
  return raw
    .split(/[\n,;]/)
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

function countBy<T>(items: T[], getKey: (item: T) => string | null | undefined): Map<string, number> {
  const result = new Map<string, number>();
  for (const item of items) {
    const key = getKey(item);
    if (!key) continue;
    result.set(key, (result.get(key) ?? 0) + 1);
  }
  return result;
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("ru-RU").format(value);
}

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)} мс`;
  return `${(ms / 1000).toFixed(1)} с`;
}

function formatDocType(type: string): string {
  const normalized = type.toLowerCase();
  if (normalized === "pdf") return "PDF";
  if (normalized === "docx" || normalized === "doc" || normalized === "docm") return "Word";
  if (normalized === "xlsx" || normalized === "xls") return "Excel";
  if (normalized === "csv") return "CSV";
  if (normalized === "markdown" || normalized === "md") return "Markdown";
  return type.toUpperCase();
}

function formatGeography(value: string | null | undefined): string {
  if (!value) return "география не указана";
  return GEOGRAPHY_LABELS[value.toLowerCase()] ?? value;
}

function shortId(value: string): string {
  return value.length > 18 ? `${value.slice(0, 9)}…${value.slice(-6)}` : value;
}

function sourceMatchesQuery(source: SourceSummary, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return [source.title, source.source_id, source.document_type, source.geography ?? ""]
    .join(" ")
    .toLowerCase()
    .includes(needle);
}

function setToArray(set: Set<string>): string[] {
  return [...set].sort((left, right) => left.localeCompare(right, "ru"));
}

function sourceCardStyle(color: string): CSSProperties {
  return { "--source-color": color } as CSSProperties;
}

function FilterChip({
  children,
  onClear,
}: {
  children: ReactNode;
  onClear?: () => void;
}) {
  return (
    <span className="filter-chip">
      {children}
      {onClear ? (
        <button aria-label="Убрать фильтр" onClick={onClear} type="button">
          <X size={12} />
        </button>
      ) : null}
    </span>
  );
}

export function AnalysisWorkbench({ injectedQuestion }: AnalysisWorkbenchProps) {
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState(defaultQuestion);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [requestStartedAt, setRequestStartedAt] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [lastDurationMs, setLastDurationMs] = useState<number | null>(null);
  const [juryMode, setJuryMode] = useState(true);
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  const [sourceQuery, setSourceQuery] = useState("");
  const [selectedGeographies, setSelectedGeographies] = useState<Set<string>>(new Set());
  const [selectedDocTypes, setSelectedDocTypes] = useState<Set<string>>(new Set());
  const [selectedLabels, setSelectedLabels] = useState<Set<string>>(
    () => new Set(["public", "internal"]),
  );
  const [materialFilter, setMaterialFilter] = useState("");
  const [propertyFilter, setPropertyFilter] = useState("");
  const [regimeFilter, setRegimeFilter] = useState("");
  const [experimentFilter, setExperimentFilter] = useState("");
  const [regimeIdFilter, setRegimeIdFilter] = useState("");
  const [yearFromFilter, setYearFromFilter] = useState("");
  const [yearToFilter, setYearToFilter] = useState("");
  const [highlightedSpanId, setHighlightedSpanId] = useState<string | null>(null);
  const [openSourceId, setOpenSourceId] = useState<string | null>(null);
  const [sourceEvidenceCache, setSourceEvidenceCache] = useState<Record<string, EvidenceSpan[]>>({});
  const [sourceEvidenceLoading, setSourceEvidenceLoading] = useState<string | null>(null);
  const [sourceEvidenceError, setSourceEvidenceError] = useState<string | null>(null);

  const sourceById = useMemo(() => {
    const map = new Map<string, SourceSummary>();
    sources.forEach((source) => map.set(source.source_id, source));
    return map;
  }, [sources]);

  const corpusStats = useMemo(
    () => ({
      sources: sources.length,
      evidence: sources.reduce((total, source) => total + source.evidence_count, 0),
      measurements: sources.reduce((total, source) => total + source.measurement_count, 0),
      running: sources.filter((source) => source.status === "running").length,
    }),
    [sources],
  );

  const geographyOptions = useMemo(() => countBy(sources, (source) => source.geography), [sources]);
  const docTypeOptions = useMemo(() => countBy(sources, (source) => source.document_type), [sources]);
  const labelOptions = useMemo(() => countBy(sources, (source) => source.security_label), [sources]);

  const sourcesMatchingUiFilters = useMemo(() => {
    return sources.filter((source) => {
      if (!sourceMatchesQuery(source, sourceQuery)) return false;
      if (selectedDocTypes.size > 0 && !selectedDocTypes.has(source.document_type)) return false;
      if (
        selectedGeographies.size > 0 &&
        (!source.geography || !selectedGeographies.has(source.geography))
      ) {
        return false;
      }
      if (selectedLabels.size > 0 && !selectedLabels.has(source.security_label)) return false;
      if (selectedSourceIds.size > 0 && !selectedSourceIds.has(source.source_id)) return false;
      return true;
    });
  }, [selectedDocTypes, selectedGeographies, selectedLabels, selectedSourceIds, sourceQuery, sources]);

  const sourceScopeActive =
    selectedSourceIds.size > 0 || sourceQuery.trim().length > 0 || selectedDocTypes.size > 0;

  const sourceIdsForBackend = useMemo(() => {
    let pool = sources;
    if (selectedSourceIds.size > 0) {
      pool = pool.filter((source) => selectedSourceIds.has(source.source_id));
    }
    if (sourceQuery.trim().length > 0) {
      pool = pool.filter((source) => sourceMatchesQuery(source, sourceQuery));
    }
    if (selectedDocTypes.size > 0) {
      pool = pool.filter((source) => selectedDocTypes.has(source.document_type));
    }
    return pool.map((source) => source.source_id);
  }, [selectedDocTypes, selectedSourceIds, sourceQuery, sources]);

  const citationIndex = useMemo(() => {
    const index = new Map<string, number>();
    answer?.evidence.forEach((span, spanIndex) => {
      index.set(span.span_id, spanIndex + 1);
    });
    return index;
  }, [answer]);

  const spanById = useMemo(() => {
    const map = new Map<string, EvidenceSpan>();
    answer?.evidence.forEach((span) => map.set(span.span_id, span));
    return map;
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

  const answerSourceGroups = useMemo<SourceGroup[]>(() => {
    const groups = new Map<string, SourceGroup>();
    answer?.evidence.forEach((span) => {
      const group =
        groups.get(span.source_id) ??
        ({
          sourceId: span.source_id,
          source: sourceById.get(span.source_id),
          spanIds: [],
          pages: new Set<number>(),
        } satisfies SourceGroup);
      group.spanIds.push(span.span_id);
      if (span.page != null) group.pages.add(span.page);
      groups.set(span.source_id, group);
    });
    return [...groups.values()].sort((left, right) => right.spanIds.length - left.spanIds.length);
  }, [answer, sourceById]);

  const activeSourcePool = sourcesMatchingUiFilters.length > 0 ? sourcesMatchingUiFilters : sources;
  const activeSource =
    activeSourcePool.length > 0 ? activeSourcePool[loadingStep % activeSourcePool.length] : null;
  const currentStep = PIPELINE_STEPS[Math.min(loadingStep, PIPELINE_STEPS.length - 1)];

  const activeFilterChips = useMemo(() => {
    const chips: Array<{ label: string; clear?: () => void }> = [];
    if (sourceQuery.trim()) chips.push({ label: `поиск источника: ${sourceQuery}`, clear: () => setSourceQuery("") });
    if (selectedSourceIds.size > 0) {
      chips.push({ label: `источники: ${selectedSourceIds.size}`, clear: () => setSelectedSourceIds(new Set()) });
    }
    for (const geography of setToArray(selectedGeographies)) {
      chips.push({
        label: formatGeography(geography),
        clear: () => toggleSetValue(setSelectedGeographies, geography),
      });
    }
    for (const docType of setToArray(selectedDocTypes)) {
      chips.push({
        label: formatDocType(docType),
        clear: () => toggleSetValue(setSelectedDocTypes, docType),
      });
    }
    if (materialFilter.trim()) chips.push({ label: `материал: ${materialFilter}`, clear: () => setMaterialFilter("") });
    if (propertyFilter.trim()) chips.push({ label: `свойство: ${propertyFilter}`, clear: () => setPropertyFilter("") });
    if (regimeFilter.trim()) chips.push({ label: `режим: ${regimeFilter}`, clear: () => setRegimeFilter("") });
    if (experimentFilter.trim()) chips.push({ label: `experiment_id: ${experimentFilter}`, clear: () => setExperimentFilter("") });
    if (regimeIdFilter.trim()) chips.push({ label: `regime_id: ${regimeIdFilter}`, clear: () => setRegimeIdFilter("") });
    if (yearFromFilter.trim() || yearToFilter.trim()) {
      chips.push({
        label: `годы: ${yearFromFilter || "…"}-${yearToFilter || "…"}`,
        clear: () => {
          setYearFromFilter("");
          setYearToFilter("");
        },
      });
    }
    return chips;
  }, [
    experimentFilter,
    materialFilter,
    propertyFilter,
    regimeFilter,
    regimeIdFilter,
    selectedDocTypes,
    selectedGeographies,
    selectedSourceIds.size,
    sourceQuery,
    yearFromFilter,
    yearToFilter,
  ]);

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0);
      setRequestStartedAt(null);
      return;
    }
    const timer = window.setInterval(() => {
      setLoadingStep((step) => step + 1);
    }, 1150);
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    if (!loading || requestStartedAt == null) {
      return;
    }
    const timer = window.setInterval(() => {
      setElapsedMs(performance.now() - requestStartedAt);
    }, 250);
    return () => window.clearInterval(timer);
  }, [loading, requestStartedAt]);

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
    if (!juryMode) return;
    setSelectedLabels((previous) => {
      const next = new Set([...previous].filter((label) => label === "public" || label === "internal"));
      if (next.size === 0) {
        next.add("public");
        next.add("internal");
      }
      return next;
    });
  }, [juryMode]);

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

  function toggleSetValue(
    setter: (next: Set<string> | ((previous: Set<string>) => Set<string>)) => void,
    value: string,
  ) {
    setter((previous: Set<string>) => {
      const next = new Set(previous);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function toggleLabel(label: SecurityLabel) {
    if (juryMode && label !== "public" && label !== "internal") return;
    toggleSetValue(setSelectedLabels, label);
  }

  function buildFilters(): AskFilters {
    const filters: AskFilters = {};
    if (sourceScopeActive && sourceIdsForBackend.length > 0) {
      filters.source_ids = sourceIdsForBackend;
    }

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
    if (selectedGeographies.size > 0) filters.geography = setToArray(selectedGeographies);

    const yearFrom = Number.parseInt(yearFromFilter, 10);
    if (!Number.isNaN(yearFrom)) filters.year_from = yearFrom;
    const yearTo = Number.parseInt(yearToFilter, 10);
    if (!Number.isNaN(yearTo)) filters.year_to = yearTo;
    return filters;
  }

  function buildAllowedLabels(): SecurityLabel[] | undefined {
    const labels = setToArray(selectedLabels) as SecurityLabel[];
    if (labels.length > 0) return labels;
    return juryMode ? ["public", "internal"] : undefined;
  }

  async function handleSubmit(nextQuestion: string) {
    const trimmed = nextQuestion.trim();
    if (!trimmed) {
      setError("Введите исследовательский вопрос.");
      return;
    }
    if (sourceScopeActive && sourceIdsForBackend.length === 0) {
      setError("Фильтры источников не оставили ни одного файла. Ослабьте поиск или тип документа.");
      return;
    }
    setLoading(true);
    setError(null);
    setHighlightedSpanId(null);
    setAnswer(null);
    const started = performance.now();
    setRequestStartedAt(started);
    setElapsedMs(0);
    try {
      setQuestion(trimmed);
      setAnswer(await askQuestion(trimmed, buildFilters(), buildAllowedLabels()));
      setLastDurationMs(performance.now() - started);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить запрос");
      setLastDurationMs(performance.now() - started);
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
    setSourceQuery("");
    setSelectedGeographies(new Set());
    setSelectedDocTypes(new Set());
    setMaterialFilter("");
    setPropertyFilter("");
    setRegimeFilter("");
    setExperimentFilter("");
    setRegimeIdFilter("");
    setYearFromFilter("");
    setYearToFilter("");
    setSelectedLabels(juryMode ? new Set(["public", "internal"]) : new Set());
  }

  async function openSource(sourceId: string) {
    setOpenSourceId(sourceId);
    setSourceEvidenceError(null);
    if (sourceEvidenceCache[sourceId]) return;
    setSourceEvidenceLoading(sourceId);
    try {
      const evidence = await fetchSourceEvidence(sourceId);
      setSourceEvidenceCache((previous) => ({ ...previous, [sourceId]: evidence }));
    } catch (err) {
      setSourceEvidenceError(err instanceof Error ? err.message : "Не удалось открыть источник");
    } finally {
      setSourceEvidenceLoading(null);
    }
  }

  function renderSourceColoredSentence(sentence: string, spanIds: string[]) {
    const citedSpans = spanIds.map((spanId) => spanById.get(spanId)).filter((span): span is EvidenceSpan => Boolean(span));
    if (citedSpans.length === 0) return sentence;
    const colors = citedSpans.map((span) => sourceColorMap.get(span.source_id) ?? SOURCE_COLORS[0]);
    const parts = splitTextIntoParts(sentence, colors.length);
    return parts.map((part, index) => (
      <span
        className="source-colored-fragment"
        key={`${part}-${index}`}
        style={{ color: colors[index] ?? colors[0] }}
        title={sourceById.get(citedSpans[index]?.source_id ?? "")?.title ?? citedSpans[index]?.source_id}
      >
        {part}
      </span>
    ));
  }

  function splitTextIntoParts(text: string, partCount: number): string[] {
    if (partCount <= 1 || text.length < 12) return [text];
    const words = text.split(/(\s+)/);
    const chunkSize = Math.ceil(words.length / partCount);
    const parts: string[] = [];
    for (let index = 0; index < partCount; index += 1) {
      parts.push(words.slice(index * chunkSize, (index + 1) * chunkSize).join(""));
    }
    return parts.filter((part) => part.length > 0);
  }

  const openSourceSummary = openSourceId ? sourceById.get(openSourceId) : undefined;
  const openSourceEvidence = openSourceId ? (sourceEvidenceCache[openSourceId] ?? []) : [];
  const verification = answer?.verification;
  const sourcePreviewLimit = loading ? 7 : 12;

  return (
    <div className="qa-workbench-pro">
      <div className="stack qa-query-console">
        <Panel title="Исследовательский запрос">
          <div className="qa-console-head qa-console-head-pro">
            <div className="qa-console-icon">
              <MessagesSquare size={22} />
            </div>
            <div>
              <div className="qa-console-title-pro">Evidence-first QA</div>
              <p>
                Запрос уходит в гибридный поиск, затем каждый ответ возвращается вместе с
                источниками, span_id и проверкой claims.
              </p>
            </div>
          </div>

          <form
            className="question-composer"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSubmit(question);
            }}
          >
            <textarea
              aria-label="Исследовательский вопрос"
              disabled={loading}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Введите вопрос жюри или исследовательский запрос..."
              value={question}
            />
            <div className="question-composer-footer">
              <button className="primary-button" disabled={loading} type="submit">
                {loading ? <Loader2 size={17} /> : <Search size={17} />}
                Запустить поиск
              </button>
              <button
                className="secondary-button"
                disabled={loading}
                onClick={() => setQuestion(defaultQuestion)}
                type="button"
              >
                <RotateCcw size={16} />
                Сбросить вопрос
              </button>
            </div>
          </form>

          <div className="jury-question-grid" aria-label="Вопросы жюри">
            {JURY_QUESTIONS.map((item) => (
              <button
                className="jury-question-button"
                disabled={loading}
                key={item.label}
                onClick={() => setQuestion(item.question)}
                type="button"
              >
                <Sparkles size={15} />
                <span>{item.label}</span>
              </button>
            ))}
          </div>

          <div className="corpus-signal-strip">
            <div>
              <Database size={16} />
              <b>{formatCount(corpusStats.sources)}</b>
              <span>источников</span>
            </div>
            <div>
              <FileSearch size={16} />
              <b>{formatCount(corpusStats.evidence)}</b>
              <span>evidence spans</span>
            </div>
            <div>
              <Table2 size={16} />
              <b>{formatCount(corpusStats.measurements)}</b>
              <span>измерений</span>
            </div>
          </div>
        </Panel>

        <Panel title="Фильтры корпуса">
          <div className="filter-toolbar-head">
            <div>
              <SlidersHorizontal size={17} />
              <span>{sourcesMatchingUiFilters.length} файлов в текущей области</span>
            </div>
            <button
              className="text-button"
              disabled={loading || activeFilterChips.length === 0}
              onClick={clearFilters}
              type="button"
            >
              Сбросить
            </button>
          </div>

          <label className="search-filter-field">
            <span>Поиск файла</span>
            <input
              disabled={loading}
              onChange={(event) => setSourceQuery(event.target.value)}
              placeholder="название, source_id, тип, страна"
              type="search"
              value={sourceQuery}
            />
          </label>

          <div className="filter-section">
            <div className="filter-section-title">
              <MapPinned size={15} />
              Страна / география источника
            </div>
            <div className="segmented-chip-grid">
              {[...geographyOptions.entries()].map(([geography, count]) => (
                <button
                  className={selectedGeographies.has(geography) ? "segmented-chip selected" : "segmented-chip"}
                  disabled={loading}
                  key={geography}
                  onClick={() => toggleSetValue(setSelectedGeographies, geography)}
                  type="button"
                >
                  <Globe2 size={14} />
                  <span>{formatGeography(geography)}</span>
                  <b>{count}</b>
                </button>
              ))}
              {geographyOptions.size === 0 ? <span className="muted-text">Метаданные географии ещё не загружены.</span> : null}
            </div>
          </div>

          <div className="filter-section">
            <div className="filter-section-title">
              <FileArchive size={15} />
              Тип документа
            </div>
            <div className="segmented-chip-grid compact">
              {[...docTypeOptions.entries()].map(([docType, count]) => (
                <button
                  className={selectedDocTypes.has(docType) ? "segmented-chip selected" : "segmented-chip"}
                  disabled={loading}
                  key={docType}
                  onClick={() => toggleSetValue(setSelectedDocTypes, docType)}
                  type="button"
                >
                  <span>{formatDocType(docType)}</span>
                  <b>{count}</b>
                </button>
              ))}
            </div>
          </div>

          <div className="filter-section">
            <div className="filter-section-title">
              <ShieldCheck size={15} />
              Метки доступа
            </div>
            <label className="mode-toggle mode-toggle-inline">
              <input
                checked={juryMode}
                disabled={loading}
                onChange={(event) => setJuryMode(event.target.checked)}
                type="checkbox"
              />
              <span>Режим жюри: только public + internal</span>
            </label>
            <div className="security-label-grid">
              {SECURITY_LABELS.map((label) => {
                const disabled = loading || (juryMode && label.value !== "public" && label.value !== "internal");
                return (
                  <button
                    className={selectedLabels.has(label.value) ? "security-label-button selected" : "security-label-button"}
                    disabled={disabled}
                    key={label.value}
                    onClick={() => toggleLabel(label.value)}
                    type="button"
                  >
                    <span>{label.label}</span>
                    <small>{labelOptions.get(label.value) ?? 0} · {label.hint}</small>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="filter-grid-pro">
            <label className="filter-text-field">
              <span>Материал / объект</span>
              <input
                disabled={loading}
                onChange={(event) => setMaterialFilter(event.target.value)}
                placeholder="шахтная вода, католит, Ni-Cu"
                type="text"
                value={materialFilter}
              />
            </label>
            <label className="filter-text-field">
              <span>Свойство / показатель</span>
              <input
                disabled={loading}
                onChange={(event) => setPropertyFilter(event.target.value)}
                placeholder="сульфаты, сухой остаток, скорость"
                type="text"
                value={propertyFilter}
              />
            </label>
            <label className="filter-text-field">
              <span>Процесс / режим</span>
              <input
                disabled={loading}
                onChange={(event) => setRegimeFilter(event.target.value)}
                placeholder="обессоливание, электроэкстракция"
                type="text"
                value={regimeFilter}
              />
            </label>
            <label className="filter-text-field">
              <span>Годы</span>
              <div className="year-range">
                <input
                  disabled={loading}
                  onChange={(event) => setYearFromFilter(event.target.value)}
                  placeholder="2020"
                  type="number"
                  value={yearFromFilter}
                />
                <input
                  disabled={loading}
                  onChange={(event) => setYearToFilter(event.target.value)}
                  placeholder="2026"
                  type="number"
                  value={yearToFilter}
                />
              </div>
            </label>
            <label className="filter-text-field">
              <span>experiment_id</span>
              <input
                disabled={loading}
                onChange={(event) => setExperimentFilter(event.target.value)}
                placeholder="exp_..."
                type="text"
                value={experimentFilter}
              />
            </label>
            <label className="filter-text-field">
              <span>regime_id</span>
              <input
                disabled={loading}
                onChange={(event) => setRegimeIdFilter(event.target.value)}
                placeholder="regime_..."
                type="text"
                value={regimeIdFilter}
              />
            </label>
          </div>

          <div className="active-filter-strip">
            {activeFilterChips.length > 0 ? (
              activeFilterChips.map((chip) => (
                <FilterChip key={chip.label} onClear={chip.clear}>
                  {chip.label}
                </FilterChip>
              ))
            ) : (
              <span className="muted-text">Фильтры не ограничивают корпус.</span>
            )}
          </div>

          <div className="source-picker-list">
            {sourcesMatchingUiFilters.slice(0, sourcePreviewLimit).map((source) => (
              <label className="source-picker-item" key={source.source_id}>
                <input
                  checked={selectedSourceIds.has(source.source_id)}
                  disabled={loading}
                  onChange={() => toggleSetValue(setSelectedSourceIds, source.source_id)}
                  type="checkbox"
                />
                <span>
                  <b>{source.title}</b>
                  <small>
                    {formatDocType(source.document_type)} · {formatGeography(source.geography)} ·{" "}
                    {source.year ?? "год неизвестен"} · {formatCount(source.evidence_count)} spans
                  </small>
                </span>
              </label>
            ))}
            {sourcesMatchingUiFilters.length === 0 ? (
              <div className="inline-empty">Нет файлов под текущие фильтры.</div>
            ) : null}
          </div>
        </Panel>
      </div>

      <div className="stack answer-stage-pro">
        <Panel title="Процесс и ответ">
          {loading ? (
            <div className="qa-process-monitor" aria-live="polite">
              <div className="process-monitor-head">
                <div>
                  <Loader2 size={18} />
                  <strong>{currentStep.title}</strong>
                  <span>{currentStep.detail}</span>
                </div>
                <div className="elapsed-clock">
                  <Clock3 size={15} />
                  {formatDuration(elapsedMs)}
                </div>
              </div>
              <div className="process-step-list">
                {PIPELINE_STEPS.map((step, index) => {
                  const state =
                    index < Math.min(loadingStep, PIPELINE_STEPS.length - 1)
                      ? "done"
                      : index === Math.min(loadingStep, PIPELINE_STEPS.length - 1)
                        ? "active"
                        : "pending";
                  return (
                    <div className={`process-step ${state}`} key={step.title}>
                      {state === "done" ? <CheckCircle2 size={15} /> : <Circle size={15} />}
                      <span>{step.title}</span>
                    </div>
                  );
                })}
              </div>
              <div className="live-request-grid">
                <div>
                  <b>{formatCount(activeSourcePool.length)}</b>
                  <span>файлов в области</span>
                </div>
                <div>
                  <b>{selectedGeographies.size || "все"}</b>
                  <span>географии</span>
                </div>
                <div>
                  <b>{setToArray(selectedLabels).join(", ") || "policy default"}</b>
                  <span>метки доступа</span>
                </div>
              </div>
              <div className="active-source-readout">
                <FileText size={16} />
                <span>
                  {activeSource
                    ? `В области поиска: ${activeSource.title}`
                    : "Ожидаю список источников от API"}
                </span>
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
            <div className="answer-result-pro">
              <div className="answer-verdict-strip answer-verdict-strip-pro">
                <div>
                  <span>Уверенность</span>
                  <strong>
                    {answer.confidence === "high"
                      ? "высокая"
                      : answer.confidence === "medium"
                        ? "средняя"
                        : "низкая"}
                  </strong>
                </div>
                <div>
                  <span>Citation coverage</span>
                  <strong>{Math.round(answer.verification.citation_coverage * 100)}%</strong>
                </div>
                <div>
                  <span>Время запроса</span>
                  <strong>{formatDuration(lastDurationMs)}</strong>
                </div>
                <div>
                  <span>Evidence</span>
                  <strong>{answer.evidence.length}</strong>
                </div>
              </div>

              {answer.answer_summary.length > 0 ? (
                <div className="source-colored-answer-list">
                  {answer.answer_summary.map((sentence, index) => {
                    const citedSpanIds = sentence.supporting_span_ids.filter((spanId) =>
                      citationIndex.has(spanId),
                    );
                    return (
                      <article
                        className="source-colored-answer-card"
                        key={`${sentence.sentence}-${index}`}
                      >
                        <p>{renderSourceColoredSentence(sentence.sentence, citedSpanIds)}</p>
                        <div className="citation-row">
                          {citedSpanIds.map((spanId) => {
                            const color = spanColorMap.get(spanId) ?? SOURCE_COLORS[0];
                            const span = spanById.get(spanId);
                            return (
                              <button
                                className="citation-chip citation-chip-source"
                                key={spanId}
                                onClick={() => focusEvidence(spanId)}
                                style={{ background: color, borderColor: color }}
                                title={`Показать доказательство ${spanId}`}
                                type="button"
                              >
                                {citationIndex.get(spanId)}
                                {span ? ` · ${formatDocType(sourceById.get(span.source_id)?.document_type ?? "src")}` : ""}
                              </button>
                            );
                          })}
                          <span className="citation-verified" title="Подтверждено доказательствами">
                            <CheckCircle2 size={12} /> проверено
                          </span>
                        </div>
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="qa-empty-state compact">
                  <FileSearch size={26} />
                  <strong>Evidence найден, но итоговый ответ не прошёл проверку</strong>
                  <span>Откройте источники справа или ослабьте фильтры для повторного запроса.</span>
                </div>
              )}

              {answer.follow_up_queries.length > 0 ? (
                <div className="follow-up-list follow-up-list-pro">
                  {answer.follow_up_queries.map((followUpQuery) => (
                    <button
                      className="secondary-button"
                      disabled={loading}
                      key={followUpQuery}
                      onClick={() => void handleSubmit(followUpQuery)}
                      type="button"
                    >
                      <ChevronRight size={15} />
                      {followUpQuery}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : !loading ? (
            <div className="qa-empty-state">
              <FileSearch size={34} />
              <strong>Запустите вопрос жюри или свой R&D запрос</strong>
              <span>
                Здесь появится текст ответа, окрашенный по источникам, плюс проверка каждой цитаты.
              </span>
            </div>
          ) : null}
        </Panel>

        {answer && answer.experiments.length > 0 ? (
          <Panel title="Структурированные эксперименты">
            <table className="experiment-table experiment-table-pro">
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
      </div>

      <div className="stack source-rail-pro">
        {artifactError ? <div className="inline-error">{artifactError}</div> : null}
        {answer ? (
          <>
            <Panel title="Файлы и источники ответа">
              <div className="source-legend-list">
                {answerSourceGroups.map((group) => {
                  const color = sourceColorMap.get(group.sourceId) ?? SOURCE_COLORS[0];
                  return (
                    <article
                      className="source-legend-card"
                      key={group.sourceId}
                      style={sourceCardStyle(color)}
                    >
                      <div className="source-legend-swatch" />
                      <div>
                        <b>{group.source?.title ?? group.sourceId}</b>
                        <span>
                          {group.source ? formatDocType(group.source.document_type) : "source"} ·{" "}
                          {formatGeography(group.source?.geography)} · {group.source?.year ?? "год неизвестен"}
                        </span>
                        <small>
                          {group.spanIds.length} cited spans
                          {group.pages.size > 0 ? ` · pages ${[...group.pages].slice(0, 4).join(", ")}` : ""}
                        </small>
                      </div>
                      <button
                        className="icon-button"
                        onClick={() => void openSource(group.sourceId)}
                        title="Открыть источник"
                        type="button"
                      >
                        <PanelRightOpen size={16} />
                      </button>
                    </article>
                  );
                })}
              </div>
            </Panel>

            {openSourceId ? (
              <Panel title="Просмотр файла">
                <div className="source-viewer-head">
                  <div>
                    <b>{openSourceSummary?.title ?? openSourceId}</b>
                    <span>
                      {openSourceSummary ? formatDocType(openSourceSummary.document_type) : "source"} ·{" "}
                      {formatGeography(openSourceSummary?.geography)} ·{" "}
                      {openSourceSummary?.security_label ?? "label n/a"}
                    </span>
                  </div>
                  <button className="text-button" onClick={() => setOpenSourceId(null)} type="button">
                    Закрыть
                  </button>
                </div>
                {sourceEvidenceLoading === openSourceId ? (
                  <div className="inline-loading">
                    <Loader2 size={16} />
                    Загружаю evidence файла
                  </div>
                ) : null}
                {sourceEvidenceError ? <div className="inline-error">{sourceEvidenceError}</div> : null}
                <div className="source-evidence-mini-list">
                  {openSourceEvidence.slice(0, 36).map((span) => {
                    const highlighted = answer.evidence.some((item) => item.span_id === span.span_id);
                    return (
                      <button
                        className={highlighted ? "source-evidence-mini active" : "source-evidence-mini"}
                        key={span.span_id}
                        onClick={() => focusEvidence(span.span_id)}
                        type="button"
                      >
                        <span>
                          {span.span_type === "table_row" ? <Table2 size={13} /> : <FileText size={13} />}
                          page {span.page ?? "-"} · {shortId(span.span_id)}
                        </span>
                        <small>{span.visible_text}</small>
                      </button>
                    );
                  })}
                </div>
              </Panel>
            ) : null}

            {answer.evidence.length > 0 ? (
              <EvidenceList
                citationIndex={citationIndex}
                evidence={answer.evidence}
                highlightedSpanId={highlightedSpanId}
                onOpenSource={(sourceId) => void openSource(sourceId)}
                sourceById={sourceById}
                sourceColorMap={sourceColorMap}
              />
            ) : null}
            {answer.graph_paths.length > 0 ? <GraphView graphPaths={answer.graph_paths} /> : null}
            <EvaluationDashboard answer={answer} />
          </>
        ) : (
          <Panel title="Что будет рядом с ответом">
            <div className="qa-result-preview qa-result-preview-pro">
              <div>
                <FileText size={18} />
                <span>Файлы-источники с цветовой легендой</span>
              </div>
              <div>
                <Network size={18} />
                <span>Графовые пути и экспериментальные строки</span>
              </div>
              <div>
                <ShieldCheck size={18} />
                <span>Метрики верификации и security-label контроль</span>
              </div>
            </div>
          </Panel>
        )}
        {verification ? (
          <Panel title="Контроль качества">
            <div className="quality-mini-grid quality-mini-grid-pro">
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
                <b>{verification.semantic_unsupported_count}</b>
                <span>semantic unsupported</span>
              </div>
            </div>
          </Panel>
        ) : null}
      </div>
    </div>
  );
}
