import { Loader2, Search } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import {
  fetchNeighborhood,
  searchEntities,
  type GraphNeighborhood as Neighborhood,
  type GraphNode,
} from "@/shared/api";
import { Panel } from "@/shared/ui";

const TYPE_COLORS: Record<string, string> = {
  material: "#0d9488",
  process: "#2563eb",
  regime: "#2563eb",
  condition: "#2563eb",
  property: "#7c3aed",
  equipment: "#0ea5e9",
  facility: "#0ea5e9",
  experiment: "#7c3aed",
  method: "#0ea5e9",
  publication: "#059669",
  patent: "#059669",
  standard: "#059669",
  person: "#2563eb",
  expert: "#2563eb",
  team: "#2563eb",
  laboratory: "#2563eb",
  organization: "#2563eb",
  location: "#0891b2",
  technology_solution: "#7c3aed",
  economic_indicator: "#d97706",
  conclusion: "#7c3aed",
  recommendation: "#059669",
  limitation: "#dc2626",
  decision: "#7c3aed",
  value: "#64748b",
};

type ForceNode = {
  id: string;
  label: string;
  entityType: string;
  evidenceCount: number;
};

type ForceLink = {
  source: string;
  target: string;
  relationType: string;
  evidenceCount: number;
};

type GraphData = { nodes: ForceNode[]; links: ForceLink[] };

function toGraphData(neighborhood: Neighborhood, previous?: GraphData): GraphData {
  const nodes = new Map<string, ForceNode>();
  const links = new Map<string, ForceLink>();
  if (previous) {
    for (const node of previous.nodes) nodes.set(node.id, node);
    for (const link of previous.links) {
      const sourceId = typeof link.source === "object" ? (link.source as { id: string }).id : link.source;
      const targetId = typeof link.target === "object" ? (link.target as { id: string }).id : link.target;
      links.set(`${sourceId}->${targetId}:${link.relationType}`, {
        source: sourceId,
        target: targetId,
        relationType: link.relationType,
        evidenceCount: link.evidenceCount,
      });
    }
  }
  for (const node of neighborhood.nodes) {
    nodes.set(node.entity_id, {
      id: node.entity_id,
      label: node.label,
      entityType: node.entity_type,
      evidenceCount: node.evidence_count,
    });
  }
  for (const edge of neighborhood.edges) {
    links.set(`${edge.source}->${edge.target}:${edge.relation_type}`, {
      source: edge.source,
      target: edge.target,
      relationType: edge.relation_type,
      evidenceCount: edge.evidence_count,
    });
  }
  return { nodes: [...nodes.values()], links: [...links.values()] };
}

function topEntries(values: Record<string, number>, limit = 6) {
  return Object.entries(values)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

export function GraphNeighborhoodPanel() {
  const [query, setQuery] = useState("шахтная вода");
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(760);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const node of data.nodes) counts[node.entityType] = (counts[node.entityType] ?? 0) + 1;
    return counts;
  }, [data.nodes]);

  const relationCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const link of data.links) counts[link.relationType] = (counts[link.relationType] ?? 0) + 1;
    return counts;
  }, [data.links]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const measured = entries[0]?.contentRect.width;
      if (measured) setWidth(measured);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const loadEntity = useCallback(async (entityId: string, merge: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const neighborhood = await fetchNeighborhood(entityId, 1, 140);
      setData((previous) => toGraphData(neighborhood, merge ? previous : undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось построить граф");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const results = await searchEntities("шахтные воды");
        if (results.length > 0) await loadEntity(results[0].entity_id, false);
      } catch {
        // initial graph is best-effort
      }
    })();
  }, [loadEntity]);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setError(null);
    try {
      const results = await searchEntities(trimmed);
      if (results.length === 0) {
        setError("Сущность не найдена");
        return;
      }
      await loadEntity(results[0].entity_id, false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Поиск не удался");
    }
  }

  return (
    <Panel title="Интерактивная карта связей">
      <div className="graph-explorer-head">
        <form className="graph-search" onSubmit={handleSearch}>
          <label className="file-control graph-search-field">
            <Search size={16} />
            <input
              className="url-input"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="шахтная вода, SO2, никель, католит…"
              value={query}
            />
          </label>
          <button className="primary-button" disabled={loading} type="submit">
            {loading ? <Loader2 size={16} /> : <Search size={16} />}
            Найти узел
          </button>
        </form>
        <div className="graph-scope-note">
          Показываем neighborhood до 140 узлов: быстро, читаемо, без попытки отрисовать весь граф.
        </div>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="graph-explorer-layout">
        <div className="graph-force-wrap graph-force-wrap-v2" ref={containerRef}>
          {data.nodes.length === 0 ? (
            <div className="status-pill">Граф пуст — загрузите документы.</div>
          ) : (
            <ForceGraph2D
              cooldownTicks={90}
              d3AlphaDecay={0.035}
              d3VelocityDecay={0.28}
              enableNodeDrag
              graphData={data}
              height={540}
              linkColor={(link) => {
                const typed = link as unknown as ForceLink;
                return typed.relationType === "DESCRIBED_IN" ? "rgba(5, 150, 105, 0.28)" : "rgba(37, 99, 235, 0.22)";
              }}
              linkDirectionalArrowLength={3}
              linkDirectionalArrowRelPos={1}
              linkLineDash={(link) => {
                const typed = link as unknown as ForceLink;
                return typed.relationType === "DESCRIBED_IN" ? [3, 4] : null;
              }}
              linkWidth={(link) => {
                const typed = link as unknown as ForceLink;
                return Math.min(1 + Math.log10((typed.evidenceCount ?? 1) + 1), 3);
              }}
              nodeCanvasObject={(node, ctx, globalScale) => {
                const typed = node as unknown as ForceNode & { x: number; y: number };
                const radius = Math.min(5 + Math.log10(typed.evidenceCount + 1) * 4, 16);
                const color = TYPE_COLORS[typed.entityType] ?? "#64748b";
                ctx.beginPath();
                ctx.arc(typed.x, typed.y, radius + 3, 0, 2 * Math.PI);
                ctx.fillStyle = "rgba(255,255,255,0.86)";
                ctx.fill();
                ctx.beginPath();
                ctx.arc(typed.x, typed.y, radius, 0, 2 * Math.PI);
                ctx.fillStyle = color;
                ctx.fill();
                if (globalScale > 0.8) {
                  ctx.font = `${Math.max(12 / globalScale, 4)}px Inter, sans-serif`;
                  ctx.fillStyle = "#0f172a";
                  ctx.textAlign = "center";
                  ctx.fillText(typed.label.slice(0, 28), typed.x, typed.y + radius + 12 / globalScale);
                }
              }}
              onNodeClick={(node) => {
                const typed = node as unknown as ForceNode;
                setSelected({
                  entity_id: typed.id,
                  entity_type: typed.entityType,
                  label: typed.label,
                  evidence_count: typed.evidenceCount,
                });
                void loadEntity(typed.id, true);
              }}
              width={width}
            />
          )}
        </div>

        <aside className="graph-side">
          <div className="graph-side-card">
            <span>Узлов в окне</span>
            <b>{data.nodes.length.toLocaleString("ru-RU")}</b>
          </div>
          <div className="graph-side-card">
            <span>Связей в окне</span>
            <b>{data.links.length.toLocaleString("ru-RU")}</b>
          </div>
          <div className="graph-node-panel graph-node-panel-v2">
            {selected ? (
              <>
                <strong>{selected.label}</strong>
                <span>{selected.entity_type}</span>
                <span>{selected.evidence_count.toLocaleString("ru-RU")} evidence</span>
              </>
            ) : (
              <>
                <strong>Кликните по узлу</strong>
                <span>Граф расширит соседей и покажет тип / evidence count.</span>
              </>
            )}
          </div>
          <div>
            <div className="graph-side-title">Типы узлов</div>
            <div className="graph-legend graph-legend-v2">
              {topEntries(typeCounts).map(([type, count]) => (
                <span className="legend-item" key={type}>
                  <span className="legend-dot" style={{ backgroundColor: TYPE_COLORS[type] ?? "#64748b" }} />
                  {type} · {count}
                </span>
              ))}
            </div>
          </div>
          <div>
            <div className="graph-side-title">Типы связей</div>
            <div className="relation-chip-list">
              {topEntries(relationCounts, 7).map(([type, count]) => (
                <span className="relation-chip" key={type}>
                  {type} <b>{count}</b>
                </span>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </Panel>
  );
}
