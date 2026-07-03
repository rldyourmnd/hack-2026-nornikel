import { FileText, FlaskConical, Layers, Tag, User } from "lucide-react";
import { useEffect, useState } from "react";

import {
  fetchEntitiesByType,
  fetchStats,
  type StatsOverview,
  type TypedEntity,
} from "@/shared/api";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "•";
}

export function ExpertsPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [experts, setExperts] = useState<TypedEntity[]>([]);
  const [labs, setLabs] = useState<TypedEntity[]>([]);
  const [orgs, setOrgs] = useState<TypedEntity[]>([]);

  useEffect(() => {
    fetchStats().then(setStats).catch(() => setStats(null));
    fetchEntitiesByType("person,expert", 12).then(setExperts).catch(() => setExperts([]));
    fetchEntitiesByType("laboratory,facility", 8).then(setLabs).catch(() => setLabs([]));
    fetchEntitiesByType("organization,team", 8).then(setOrgs).catch(() => setOrgs([]));
  }, []);

  const byType = stats?.entities_by_type ?? {};
  const statCards = [
    { Icon: User, value: (byType.person ?? 0) + (byType.expert ?? 0), label: "Эксперты" },
    { Icon: FlaskConical, value: (byType.laboratory ?? 0) + (byType.facility ?? 0), label: "Лаборатории" },
    { Icon: FileText, value: byType.publication ?? 0, label: "Публикации" },
    { Icon: Layers, value: (byType.organization ?? 0) + (byType.team ?? 0), label: "Организации" },
  ];

  return (
    <div className="page-wrap">
      <section className="page-hero">
        <div className="page-hero-main">
          <div className="page-hero-eyebrow">Носители экспертизы</div>
          <h1 className="page-hero-title">Эксперты и лаборатории</h1>
          <p className="page-hero-caption">
            Кто в организации создаёт знания и несёт экспертизу — через публикации, проекты и связи
            с материалами, процессами и темами.
          </p>
        </div>
        <div className="hero-mascot-card">
          <img alt="" className="hero-mascot-img" src="/brand/mascot-span.png" />
          <span>Если граф молчит — ищем носителя экспертизы</span>
        </div>
      </section>

      <div className="stat-grid stat-grid-4">
        {statCards.map(({ Icon, value, label }) => (
          <div className="metric-card" key={label}>
            <div className="metric-card-icon">
              <Icon size={20} />
            </div>
            <div>
              <div className="metric-card-value">{value.toLocaleString("ru-RU")}</div>
              <div className="metric-card-label">{label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="experts-grid">
        <section className="panel experts-rank">
          <div className="panel-header">
            <span className="panel-title">Кого спросить</span>
          </div>
          <div className="panel-body">
            <p className="muted-note">Рекомендованные эксперты по частоте упоминаний в корпусе.</p>
            {experts.length === 0 ? (
              <p className="muted-note">Эксперты появятся после обогащения корпуса.</p>
            ) : (
              <ol className="expert-rank-list">
                {experts.slice(0, 6).map((expert, index) => (
                  <li className="expert-rank-item" key={expert.entity_id}>
                    <span className="expert-rank-n">{index + 1}</span>
                    <span className="expert-avatar">{initials(expert.canonical_name)}</span>
                    <span className="expert-rank-body">
                      <span className="expert-rank-name">{expert.canonical_name}</span>
                      <span className="expert-rank-sub">
                        {expert.evidence_count} упоминаний в источниках
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <span className="panel-title">Лаборатории и организации</span>
          </div>
          <div className="panel-body">
            <div className="lab-card-grid">
              {[...labs, ...orgs].slice(0, 6).map((lab) => (
                <article className="lab-card" key={lab.entity_id}>
                  <div className="lab-card-icon">
                    <FlaskConical size={18} />
                  </div>
                  <div className="lab-card-name">{lab.canonical_name}</div>
                  <div className="lab-card-meta">
                    <FileText size={13} /> {lab.evidence_count} упоминаний
                  </div>
                </article>
              ))}
              {labs.length === 0 && orgs.length === 0 ? (
                <p className="muted-note">Лаборатории и организации извлекаются из аффилиаций.</p>
              ) : null}
            </div>
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <span className="panel-title">Связанные темы</span>
        </div>
        <div className="panel-body">
          <div className="topic-chip-row">
            {["Гидрометаллургия", "Обеднение шлака", "Электроэкстракция", "Обогащение руд", "Коррозия и защита", "Переработка отходов"].map(
              (topic) => (
                <span className="topic-chip" key={topic}>
                  <Tag size={13} /> {topic}
                </span>
              ),
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
