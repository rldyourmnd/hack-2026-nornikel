import { Building2, FileText, FlaskConical, Layers, Search, Tag, User } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  fetchEntitiesByType,
  fetchNeighborhood,
  fetchStats,
  searchEntities,
  type EntitySearchResult,
  type GraphNeighborhood,
  type StatsOverview,
  type TypedEntity,
} from "@/shared/api";

type ExpertCandidate = {
  entity_id: string;
  entity_type: string;
  canonical_name: string;
  evidence_count?: number;
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "•";
}

function toCandidate(entity: TypedEntity | EntitySearchResult): ExpertCandidate {
  return {
    entity_id: entity.entity_id,
    entity_type: entity.entity_type,
    canonical_name: entity.canonical_name,
    evidence_count: "evidence_count" in entity ? entity.evidence_count : undefined,
  };
}

function formatNumber(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString("ru-RU");
}

export function ExpertsPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [experts, setExperts] = useState<TypedEntity[]>([]);
  const [labs, setLabs] = useState<TypedEntity[]>([]);
  const [orgs, setOrgs] = useState<TypedEntity[]>([]);
  const [query, setQuery] = useState("Воробьёв");
  const [searchResults, setSearchResults] = useState<ExpertCandidate[]>([]);
  const [selected, setSelected] = useState<ExpertCandidate | null>(null);
  const [neighborhood, setNeighborhood] = useState<GraphNeighborhood | null>(null);
  const [expertLoading, setExpertLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([
      fetchStats(),
      fetchEntitiesByType("person,expert", 18),
      fetchEntitiesByType("laboratory,facility", 10),
      fetchEntitiesByType("organization,team", 10),
    ])
      .then(([nextStats, nextExperts, nextLabs, nextOrgs]) => {
        setStats(nextStats);
        setExperts(nextExperts);
        setLabs(nextLabs);
        setOrgs(nextOrgs);
        setSearchResults(nextExperts.map(toCandidate));
        setSelected(toCandidate(nextExperts[1] ?? nextExperts[0]));
      })
      .catch(() => {
        setStats(null);
        setExperts([]);
        setLabs([]);
        setOrgs([]);
      });
  }, []);

  useEffect(() => {
    if (!selected) {
      return;
    }
    setExpertLoading(true);
    setNeighborhood(null);
    void fetchNeighborhood(selected.entity_id, 1, 90)
      .then(setNeighborhood)
      .catch((err) => {
        setNeighborhood(null);
        setError(err instanceof Error ? err.message : "Не удалось построить связи эксперта");
      })
      .finally(() => setExpertLoading(false));
  }, [selected]);

  const byType = stats?.entities_by_type ?? {};
  const statCards = [
    { Icon: User, value: (byType.person ?? 0) + (byType.expert ?? 0), label: "людей и экспертов" },
    { Icon: FlaskConical, value: (byType.laboratory ?? 0) + (byType.facility ?? 0), label: "лабораторий / площадок" },
    { Icon: FileText, value: byType.publication ?? 0, label: "публикаций" },
    { Icon: Layers, value: (byType.organization ?? 0) + (byType.team ?? 0), label: "организаций" },
  ];

  const relatedPublications = useMemo(
    () =>
      (neighborhood?.nodes ?? [])
        .filter((node) => node.entity_type === "publication")
        .sort((a, b) => b.evidence_count - a.evidence_count)
        .slice(0, 8),
    [neighborhood],
  );

  const relatedTopics = useMemo(
    () =>
      (neighborhood?.nodes ?? [])
        .filter((node) => ["material", "process", "technology_solution", "property", "organization"].includes(node.entity_type))
        .sort((a, b) => b.evidence_count - a.evidence_count)
        .slice(0, 12),
    [neighborhood],
  );

  async function runSearch() {
    const trimmed = query.trim();
    setError(null);
    if (!trimmed) {
      const defaults = experts.map(toCandidate);
      setSearchResults(defaults);
      setSelected(defaults[1] ?? defaults[0] ?? null);
      return;
    }
    try {
      const results = (await searchEntities(trimmed))
        .filter((entity) => ["person", "expert", "organization", "laboratory", "facility"].includes(entity.entity_type))
        .map(toCandidate);
      setSearchResults(results);
      setSelected(results[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Поиск экспертов не выполнен");
    }
  }

  return (
    <div className="page-wrap experts-page-v2">
      <section className="experts-hero-v2">
        <div>
          <div className="section-eyebrow">Expert graph</div>
          <h1>Эксперты, организации и файлы, где они встречаются</h1>
          <p>
            Поиск идёт по реальным сущностям полного графа. При выборе эксперта показываем его
            публикации, связанные темы и плотность evidence, а не статический список.
          </p>
        </div>
        <div className="expert-search-console">
          <label>
            Поиск по ФИО, организации или лаборатории
            <span>
              <Search size={16} />
              <input
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    void runSearch();
                  }
                }}
                value={query}
              />
            </span>
          </label>
          <button className="primary-button" onClick={() => void runSearch()} type="button">
            Найти в графе
          </button>
        </div>
      </section>

      <div className="stat-grid stat-grid-4">
        {statCards.map(({ Icon, value, label }) => (
          <div className="metric-card" key={label}>
            <div className="metric-card-icon">
              <Icon size={20} />
            </div>
            <div>
              <div className="metric-card-value">{formatNumber(value)}</div>
              <div className="metric-card-label">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="experts-lab-layout">
        <section className="expert-directory panel-glass">
          <div className="panel-header-row">
            <strong>Результаты поиска</strong>
            <span>{searchResults.length || experts.length} candidates</span>
          </div>
          <div className="expert-rank-list v2">
            {(searchResults.length ? searchResults : experts.map(toCandidate)).slice(0, 14).map((expert, index) => (
              <button
                className={`expert-rank-item ${selected?.entity_id === expert.entity_id ? "active" : ""}`}
                key={expert.entity_id}
                onClick={() => setSelected(expert)}
                type="button"
              >
                <span className="expert-rank-n">{index + 1}</span>
                <span className="expert-avatar">{initials(expert.canonical_name)}</span>
                <span className="expert-rank-body">
                  <span className="expert-rank-name">{expert.canonical_name}</span>
                  <span className="expert-rank-sub">
                    {expert.entity_type} · {expert.evidence_count ? `${expert.evidence_count} упоминаний` : "найдено поиском"}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="expert-detail-panel panel-glass">
          {selected ? (
            <>
              <div className="expert-profile-head">
                <span className="expert-avatar large">{initials(selected.canonical_name)}</span>
                <div>
                  <div className="section-eyebrow">selected entity</div>
                  <h2>{selected.canonical_name}</h2>
                  <p>{selected.entity_type} · neighborhood depth 1 · {expertLoading ? "загружаем связи" : `${neighborhood?.nodes.length ?? 0} узлов рядом`}</p>
                </div>
              </div>

              <div className="expert-detail-grid">
                <div>
                  <h3>Файлы и публикации</h3>
                  {expertLoading ? (
                    <div className="qa-empty-state compact">Загружаем публикации и файлы из графа…</div>
                  ) : relatedPublications.length > 0 ? (
                    <div className="publication-link-list">
                      {relatedPublications.map((publication) => (
                        <article key={publication.entity_id}>
                          <FileText size={16} />
                          <div>
                            <strong>{publication.label}</strong>
                            <span>{publication.evidence_count} evidence links</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="muted-note">В первом neighborhood нет публикаций; выберите другого эксперта из списка.</p>
                  )}
                </div>
                <div>
                  <h3>Темы и организации рядом</h3>
                  <div className="topic-chip-row dense">
                    {relatedTopics.map((topic) => (
                      <span className="topic-chip" key={topic.entity_id}>
                        {topic.entity_type === "organization" ? <Building2 size={13} /> : <Tag size={13} />}
                        {topic.label}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="qa-empty-state compact">Выберите эксперта или выполните поиск.</div>
          )}
        </section>
      </div>

      <section className="panel-glass expert-org-strip">
        {[...labs, ...orgs].slice(0, 10).map((entity) => (
          <article className="lab-card" key={entity.entity_id}>
            <div className="lab-card-icon">
              <FlaskConical size={18} />
            </div>
            <div className="lab-card-name">{entity.canonical_name}</div>
            <div className="lab-card-meta">
              <FileText size={13} /> {entity.evidence_count} упоминаний
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
