import { useEffect, useState } from "react";

import { fetchStats, type StatsOverview } from "@/shared/api";
import { PageHero, Panel } from "@/shared/ui";

const EXPERT_TYPES: Array<{ key: string; label: string }> = [
  { key: "person", label: "Эксперты" },
  { key: "expert", label: "Носители экспертизы" },
  { key: "team", label: "Команды" },
  { key: "laboratory", label: "Лаборатории" },
  { key: "organization", label: "Организации" },
  { key: "publication", label: "Публикации" },
];

export function ExpertsPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  const byType = stats?.entities_by_type ?? {};

  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Носители экспертизы"
        title="Эксперты и лаборатории"
        caption="Кто в организации является носителем экспертизы по теме — через публикации, проекты и факты."
      />
      <div className="stat-grid">
        {EXPERT_TYPES.map(({ key, label }) => (
          <div className="stat-card" key={key}>
            <div className="stat-value">{byType[key] ?? 0}</div>
            <div className="stat-label">{label}</div>
          </div>
        ))}
      </div>
      <Panel title="Рекомендация экспертов">
        <p className="muted-note">
          Эксперты и лаборатории извлекаются из корпуса как графовые сущности (person / team /
          laboratory / organization) со связями AUTHORED_BY, MEMBER_OF и EXPERT_IN. Откройте раздел
          «Граф знаний», чтобы увидеть, кто связан с интересующей темой, и по каким публикациям.
        </p>
      </Panel>
    </div>
  );
}
