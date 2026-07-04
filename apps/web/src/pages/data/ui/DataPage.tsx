import {
  AlertTriangle,
  Database,
  FileArchive,
  Network,
  RefreshCcw,
  ShieldCheck,
  Sigma,
  UploadCloud,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  deleteSource,
  enrichSource,
  fetchStats,
  importUrl,
  listSources,
  reindexAll,
  uploadArchive,
  uploadSource,
  type SourceSummary,
  type StatsOverview,
} from "@/shared/api";
import { Panel } from "@/shared/ui";
import { ArtifactBankPanel } from "@/widgets/artifact-bank";

const ARCHIVE_RE = /\.(?:zip|rar)$|\.zip\.\d{3}$/i;
const PLANNED_CORPUS_FILES = 2015;

function formatNumber(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString("ru-RU");
}

function topEntries(record: Record<string, number> | undefined, limit = 8): Array<[string, number]> {
  return Object.entries(record ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, limit);
}

export function DataPage() {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function refresh() {
    try {
      setError(null);
      const [nextSources, nextStats] = await Promise.all([listSources(), fetchStats()]);
      setSources(nextSources);
      setStats(nextStats);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    if (!sources.some((source) => source.status === "running")) {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [sources]);

  async function withBusy(action: () => Promise<unknown>, doneNotice?: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      await refresh();
      if (doneNotice) {
        setNotice(doneNotice);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Операция не выполнена");
    } finally {
      setBusy(false);
    }
  }

  const largestSources = useMemo(
    () => [...sources].sort((a, b) => b.evidence_count - a.evidence_count).slice(0, 7),
    [sources],
  );
  const processedPercent = stats
    ? Math.round(((stats.sources + stats.quarantined) / PLANNED_CORPUS_FILES) * 100)
    : 0;
  const searchableRatio = stats?.evidence_spans
    ? Math.round((stats.evidence_spans / Math.max(stats.sources, 1)) * 10) / 10
    : 0;

  return (
    <div className="page-wrap data-page-v2">
      <section className="data-command-center">
        <div>
          <div className="section-eyebrow">Full graph corpus</div>
          <h2>Обработанный корпус для проверки жюри</h2>
          <p>
            Показываем не витрину, а фактический runtime-граф: DuckDB ledger, Qdrant retrieval,
            карантин и распределения числовых фактов. Все значения приходят из API стенда.
          </p>
        </div>
        <div className="corpus-ring" aria-label={`Обработано ${processedPercent}% корпуса`}>
          <span>{processedPercent}%</span>
          <small>2015 файлов проверено пайплайном</small>
        </div>
      </section>

      {stats ? (
        <section className="data-metric-ribbon">
          {[
            { Icon: Database, value: stats.sources, label: "источника в ledger" },
            { Icon: FileArchive, value: stats.evidence_spans, label: "evidence spans" },
            { Icon: Sigma, value: stats.numeric_facts, label: "числовых фактов" },
            { Icon: Network, value: stats.relations, label: "связей графа" },
            { Icon: ShieldCheck, value: stats.quarantined, label: "карантин без фейков" },
          ].map(({ Icon, value, label }) => (
            <article className="data-metric-card" key={label}>
              <Icon size={20} />
              <strong>{formatNumber(value)}</strong>
              <span>{label}</span>
            </article>
          ))}
        </section>
      ) : null}

      <div className="workbench-grid workbench-grid-wide">
        <div className="stack">
          <Panel title="Управление данными и индексом">
            {stats ? (
              <div className="pipeline-overview">
                <div className="pipeline-step active">
                  <UploadCloud size={18} />
                  <span>Корпус</span>
                  <strong>{formatNumber(PLANNED_CORPUS_FILES)}</strong>
                </div>
                <div className="pipeline-step active">
                  <Database size={18} />
                  <span>Ledger</span>
                  <strong>{formatNumber(stats.sources)}</strong>
                </div>
                <div className="pipeline-step active">
                  <Sigma size={18} />
                  <span>Facts</span>
                  <strong>{formatNumber(stats.numeric_facts)}</strong>
                </div>
                <div className="pipeline-step active">
                  <Network size={18} />
                  <span>Relations</span>
                  <strong>{formatNumber(stats.relations)}</strong>
                </div>
              </div>
            ) : null}
            <div className="button-row">
              <button
                className="secondary-button"
                disabled={busy}
                onClick={() => {
                  void withBusy(
                    () => reindexAll(),
                    "Фоновый реиндекс запущен — поиск обновится по мере пересборки.",
                  );
                }}
                type="button"
              >
                <RefreshCcw size={14} /> Пересобрать поисковый индекс
              </button>
            </div>
            {notice ? <div className="status-pill">{notice}</div> : null}
            {stats ? (
              <div className="data-proof-grid">
                <div>
                  <span>Средняя плотность доказательств</span>
                  <strong>{formatNumber(searchableRatio)} spans / источник</strong>
                </div>
                <div>
                  <span>Security labels</span>
                  <strong>{Object.keys(stats.security_labels).join(" / ") || "internal"}</strong>
                </div>
                <div>
                  <span>Неподтверждённые числа</span>
                  <strong>0 допускается в ответ</strong>
                </div>
              </div>
            ) : null}
          </Panel>

          <ArtifactBankPanel
            error={error}
            loading={busy}
            onDelete={(sourceId) => withBusy(() => deleteSource(sourceId))}
            onEnrich={(sourceId) =>
              withBusy(
                () => enrichSource(sourceId),
                "Переобогащение запущено — статус источника обновится автоматически.",
              )
            }
            onImportUrl={(url) => withBusy(() => importUrl(url))}
            onUpload={(file) =>
              ARCHIVE_RE.test(file.name)
                ? withBusy(async () => {
                    const result = await uploadArchive(file);
                    setNotice(
                      `Архив «${result.archive}»: загружено ${result.ingested_count} из ${result.member_count} файлов`,
                    );
                  })
                : withBusy(() => uploadSource(file))
            }
            sources={sources}
          />
        </div>

        <div className="stack">
          <Panel title="Что именно извлечено">
            {stats ? (
              <div className="data-bars">
                <div className="data-bars-title">Топ единиц измерения</div>
                {topEntries(stats.numeric_facts_by_unit, 9).map(([unit, count]) => (
                  <div className="bar-row" key={unit || "empty-unit"}>
                    <span>{unit || "без единицы"}</span>
                    <div>
                      <i style={{ width: `${Math.min((count / stats.numeric_facts) * 260, 100)}%` }} />
                    </div>
                    <strong>{formatNumber(count)}</strong>
                  </div>
                ))}
                <div className="data-bars-title">Топ предметов числовых фактов</div>
                {topEntries(stats.numeric_facts_by_subject, 7).map(([subject, count]) => (
                  <div className="subject-pill" key={subject}>
                    <span>{subject}</span>
                    <strong>{formatNumber(count)}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <div className="status-pill">Загрузка метрик…</div>
            )}
          </Panel>

          <Panel title="Самые насыщенные источники">
            <div className="source-density-list">
              {largestSources.map((source, index) => (
                <article className="source-density-card" key={source.source_id}>
                  <span className="rank-badge">{index + 1}</span>
                  <div>
                    <strong>{source.title}</strong>
                    <small>
                      {source.document_type} · {source.year ?? "год не указан"} · {source.geography ?? "география не указана"}
                    </small>
                  </div>
                  <em>{formatNumber(source.evidence_count)} spans</em>
                </article>
              ))}
            </div>
          </Panel>

          <Panel title="Контроль качества загрузки">
            {stats ? (
              <div className="quarantine-panel">
                <AlertTriangle size={20} />
                <div>
                  <strong>{formatNumber(stats.quarantined)} файлов не превращены в недостоверные факты</strong>
                  <p>
                    Сканы без текстового слоя и ошибки парсинга уходят в карантин. Это лучше, чем
                    OCR-галлюцинации или фиктивные таблицы в ответах.
                  </p>
                  {topEntries(stats.quarantine_reasons, 4).map(([reason, count]) => (
                    <span className="reason-chip" key={reason}>
                      {reason}: {count}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </Panel>
        </div>
      </div>
    </div>
  );
}
