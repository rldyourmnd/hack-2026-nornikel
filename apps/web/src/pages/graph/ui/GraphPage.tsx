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
    <div className="workbench-grid">
      <div className="stack">
        <GraphNeighborhoodPanel />
      </div>
      <div className="stack">
        {stats ? (
          <>
            <Panel title="Сущности графа">
              <div className="kv-list">
                {Object.entries(stats.entities_by_type).map(([type, count]) => (
                  <div className="kv-row" key={type}>
                    <span>{TYPE_LABELS[type] ?? type}</span>
                    <span className="kv-value">{count}</span>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Типы связей">
              <div className="kv-list">
                {Object.entries(stats.relations_by_type).map(([type, count]) => (
                  <div className="kv-row" key={type}>
                    <span>{type}</span>
                    <span className="kv-value">{count}</span>
                  </div>
                ))}
              </div>
              <p className="page-caption">
                Каждая связь хранит список EvidenceSpan — доказательства кликабельны до
                конкретной строки документа. DESCRIBED_IN связывает сущности с
                публикациями, AUTHORED_BY — публикации с экспертами.
              </p>
            </Panel>
          </>
        ) : (
          <Panel title="Сущности графа">
            <div className="status-pill">Загрузка статистики…</div>
          </Panel>
        )}
      </div>
    </div>
  );
}
