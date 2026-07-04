import { Loader2, Search } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import {
  fetchNeighborhood,
  searchEntities,
  type GraphNeighborhood as Neighborhood,
  type GraphNode,
} from "@/shared/api";
import { Panel } from "@/shared/ui";

// Aligned with the entity-color tokens in shared/config/nav.ts / theme.css.
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
    });
  }
  return { nodes: [...nodes.values()], links: [...links.values()] };
}

export function GraphNeighborhoodPanel() {
  const [query, setQuery] = useState("Ni-30Cu");
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(600);

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
      const neighborhood = await fetchNeighborhood(entityId, 1, 80);
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
        const results = await searchEntities("Ni-30Cu");
        if (results.length > 0) {
          await loadEntity(results[0].entity_id, false);
        }
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
    <Panel title="Граф знаний">
      <form className="upload-row" onSubmit={handleSearch}>
        <label className="file-control">
          <Search size={16} />
          <input
            className="url-input"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Материал, режим, свойство, команда…"
            value={query}
          />
        </label>
        <button className="secondary-button" disabled={loading} type="submit">
          {loading ? <Loader2 size={16} /> : <Search size={16} />}
          Найти
        </button>
      </form>
      {error ? <div className="inline-error">{error}</div> : null}
      <div className="graph-force-wrap" ref={containerRef}>
        {data.nodes.length === 0 ? (
          <div className="status-pill">Граф пуст — загрузите документы.</div>
        ) : (
          <ForceGraph2D
            graphData={data}
            height={380}
            linkColor={() => "#cbd5e1"}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const typed = node as unknown as ForceNode & { x: number; y: number };
              const radius = Math.min(4 + typed.evidenceCount, 10);
              ctx.beginPath();
              ctx.arc(typed.x, typed.y, radius, 0, 2 * Math.PI);
              ctx.fillStyle = TYPE_COLORS[typed.entityType] ?? "#64748b";
              ctx.fill();
              if (globalScale > 1.2) {
                ctx.font = `${Math.max(10 / globalScale, 3)}px Inter, sans-serif`;
                ctx.fillStyle = "#334155";
                ctx.textAlign = "center";
                ctx.fillText(typed.label.slice(0, 24), typed.x, typed.y + radius + 6 / globalScale);
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
      <div className="graph-legend">
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <span className="legend-item" key={type}>
            <span className="legend-dot" style={{ backgroundColor: color }} />
            {type}
          </span>
        ))}
      </div>
      {selected ? (
        <div className="graph-node-panel">
          <strong>{selected.label}</strong> · {selected.entity_type} ·{" "}
          {selected.evidence_count} evidence · клик по узлу расширяет соседей
        </div>
      ) : null}
    </Panel>
  );
}
