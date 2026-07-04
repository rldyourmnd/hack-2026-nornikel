import { useEffect, useState } from "react";

import { fetchStats, type StatsOverview } from "@/shared/api";
import { Panel } from "@/shared/ui";
import { GraphNeighborhoodPanel } from "@/widgets/graph-view";

const TYPE_LABELS: Record<string, string> = {
  material: "Материалы",
  process: "Процессы",
  regime: "Режимы",
  condition: "Условия",
  property: "Свойства и параметры",
  equipment: "Оборудование",
  facility: "Установки и цеха",
  experiment: "Эксперименты",
  method: "Методы",
  publication: "Публикации",
  patent: "Патенты",
  standard: "Стандарты",
  person: "Эксперты",
  expert: "Носители экспертизы",
  team: "Команды",
  laboratory: "Лаборатории",
  organization: "Организации",
  location: "География",
  technology_solution: "Технические решения",
  economic_indicator: "Экономические показатели",
  conclusion: "Выводы",
  recommendation: "Рекомендации",
  limitation: "Ограничения",
  decision: "Решения",
  value: "Значения",
};

export function GraphPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setStats(await fetchStats());
      } catch {
        // stats are additive; the explorer works without them
      }
    })();
  }, []);

  return (
    <div className="page-wrap graph-page">
      {stats ? (
        <section className="graph-kpi-strip">
          <div>
            <b>{Object.values(stats.entities_by_type).reduce((sum, value) => sum + value, 0).toLocaleString("ru-RU")}</b>
            <span>сущностей</span>
          </div>
          <div>
            <b>{stats.relations.toLocaleString("ru-RU")}</b>
            <span>связей</span>
          </div>
          <div>
            <b>{stats.evidence_spans.toLocaleString("ru-RU")}</b>
            <span>evidence spans</span>
          </div>
          <div>
            <b>{stats.numeric_facts.toLocaleString("ru-RU")}</b>
            <span>числовых фактов</span>
          </div>
        </section>
      ) : null}

      <GraphNeighborhoodPanel />

      <div className="workbench-grid">
        <Panel title="Сущности графа">
          {stats ? (
            <div className="kv-list kv-list-rich">
              {Object.entries(stats.entities_by_type)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 14)
                .map(([type, count]) => (
                  <div className="kv-row" key={type}>
                    <span>{TYPE_LABELS[type] ?? type}</span>
                    <span className="kv-value">{count.toLocaleString("ru-RU")}</span>
                  </div>
                ))}
            </div>
          ) : (
            <div className="status-pill">Загрузка статистики…</div>
          )}
        </Panel>
        <Panel title="Связи и доказательства">
          {stats ? (
            <div className="kv-list kv-list-rich">
              {Object.entries(stats.relations_by_type)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 14)
                .map(([type, count]) => (
                  <div className="kv-row" key={type}>
                    <span>{type}</span>
                    <span className="kv-value">{count.toLocaleString("ru-RU")}</span>
                  </div>
                ))}
            </div>
          ) : null}
          <p className="page-caption">
            В браузере отображается не весь граф, а оптимизированный neighborhood. Полный граф
            хранится в DuckDB; Qdrant используется только как retrieval-index для evidence spans.
          </p>
        </Panel>
      </div>
    </div>
  );
}
