import { BarChart3, Clock3, Database, GitBranch, Network, Sigma, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchStats, listAnswerRuns, type AnswerRunSummary, type StatsOverview } from "@/shared/api";
import { Panel } from "@/shared/ui";
import { GapsBoard } from "@/widgets/gaps-board";
import { DecisionsTimeline } from "@/widgets/timeline";

type AnalyticsPageProps = {
  onGapQuery: (question: string) => void;
};

function formatNumber(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString("ru-RU");
}

function topEntries(record: Record<string, number> | undefined, limit = 8): Array<[string, number]> {
  return Object.entries(record ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, limit);
}

function humanType(value: string): string {
  return value.replaceAll("_", " ");
}

export function AnalyticsPage({ onGapQuery }: AnalyticsPageProps) {
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [runs, setRuns] = useState<AnswerRunSummary[]>([]);

  useEffect(() => {
    void Promise.all([fetchStats(), listAnswerRuns(8)])
      .then(([nextStats, nextRuns]) => {
        setStats(nextStats);
        setRuns(nextRuns);
      })
      .catch(() => {
        setStats(null);
        setRuns([]);
      });
  }, []);

  const graphDensity = useMemo(() => {
    if (!stats?.sources) {
      return 0;
    }
    return Math.round((stats.relations / stats.sources) * 10) / 10;
  }, [stats]);

  const factDensity = useMemo(() => {
    if (!stats?.sources) {
      return 0;
    }
    return Math.round((stats.numeric_facts / stats.sources) * 10) / 10;
  }, [stats]);

  return (
    <div className="page-wrap analytics-page-v2">
      {stats ? (
        <section className="analytics-hero-grid">
          {[
            { Icon: Database, value: stats.sources, label: "источников", hint: "реально в DuckDB" },
            { Icon: Sigma, value: stats.numeric_facts, label: "числовых фактов", hint: "с единицами и субъектами" },
            { Icon: Network, value: stats.relations, label: "связей", hint: `${formatNumber(graphDensity)} на источник` },
            { Icon: Sparkles, value: factDensity, label: "facts/source", hint: "плотность извлечения" },
          ].map(({ Icon, value, label, hint }) => (
            <article className="analytics-hero-card" key={label}>
              <Icon size={22} />
              <strong>{formatNumber(value)}</strong>
              <span>{label}</span>
              <small>{hint}</small>
            </article>
          ))}
        </section>
      ) : null}

      <div className="analytics-main-grid">
        <Panel title="Карта знаний по типам сущностей">
          {stats ? (
            <div className="entity-spectrum">
              {topEntries(stats.entities_by_type, 12).map(([type, count], index) => (
                <div className="spectrum-row" key={type}>
                  <span>{humanType(type)}</span>
                  <div>
                    <i style={{ width: `${Math.max(8, Math.min((count / Math.max(stats.sources, 1)) * 7, 100))}%` }} />
                  </div>
                  <strong>{formatNumber(count)}</strong>
                  <em>#{index + 1}</em>
                </div>
              ))}
            </div>
          ) : (
            <div className="status-pill">Загрузка аналитики…</div>
          )}
        </Panel>

        <Panel title="Связи, которые объясняют ответы">
          {stats ? (
            <div className="relation-orbit-list">
              {topEntries(stats.relations_by_type, 10).map(([type, count]) => (
                <article className="relation-orbit" key={type}>
                  <GitBranch size={17} />
                  <div>
                    <strong>{humanType(type)}</strong>
                    <span>{formatNumber(count)} edges</span>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </Panel>
      </div>

      <div className="workbench-grid workbench-grid-wide">
        <div className="stack">
          <Panel title="Числовая аналитика корпуса">
            {stats ? (
              <div className="fact-grid">
                {topEntries(stats.numeric_facts_by_subject, 9).map(([subject, count]) => (
                  <article className="fact-topic-card" key={subject}>
                    <BarChart3 size={18} />
                    <strong>{subject}</strong>
                    <span>{formatNumber(count)} facts</span>
                  </article>
                ))}
              </div>
            ) : null}
          </Panel>
          <GapsBoard onGapQuery={onGapQuery} />
        </div>

        <div className="stack">
          <Panel title="Последние ответы и нагрузка QA">
            {runs.length > 0 ? (
              <div className="answer-run-list">
                {runs.map((run) => (
                  <article className="answer-run-card" key={run.run_id}>
                    <Clock3 size={16} />
                    <div>
                      <strong>{run.question}</strong>
                      <span>
                        {run.answer_mode ?? "qa"} · {run.latency_ms ? `${Math.round(run.latency_ms / 1000)} c` : "latency n/a"}
                      </span>
                    </div>
                    <em>{new Date(run.created_at).toLocaleString("ru-RU")}</em>
                  </article>
                ))}
              </div>
            ) : (
              <div className="qa-empty-state compact">
                Запросы появятся после демонстрационных прогонов. Сам граф уже доступен для поиска.
              </div>
            )}
          </Panel>
          <DecisionsTimeline />
        </div>
      </div>
    </div>
  );
}
