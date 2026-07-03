from __future__ import annotations

from typing import Any

import networkx as nx

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository


class GraphService:
    """On-demand NetworkX materialization of the DuckDB entity/relation layer."""

    def __init__(self, repository: DuckDBLedgerRepository) -> None:
        self.repository = repository

    def build_graph(self) -> nx.MultiDiGraph:
        graph: nx.MultiDiGraph = nx.MultiDiGraph()
        for entity in self.repository.list_graph_entities():
            graph.add_node(
                entity["entity_id"],
                entity_type=entity["entity_type"],
                label=entity["canonical_name"],
                evidence_count=entity["evidence_count"],
            )
        for relation in self.repository.list_graph_relations():
            if relation["src_entity_id"] not in graph or relation["dst_entity_id"] not in graph:
                continue
            graph.add_edge(
                relation["src_entity_id"],
                relation["dst_entity_id"],
                key=relation["relation_id"],
                relation_type=relation["relation_type"],
                evidence_count=len(relation["evidence_span_ids"]),
                confidence=relation["confidence"],
            )
        return graph

    def neighborhood(
        self,
        entity_id: str,
        *,
        depth: int = 1,
        limit: int = 100,
    ) -> dict[str, Any] | None:
        graph = self.build_graph()
        if entity_id not in graph:
            return None
        depth = max(1, min(depth, 2))
        undirected = graph.to_undirected(as_view=True)
        nodes = {entity_id}
        frontier = {entity_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                next_frontier.update(undirected.neighbors(node))
            nodes.update(next_frontier)
            frontier = next_frontier
            if len(nodes) >= limit:
                break
        # Keep the focus node plus highest-evidence neighbors within the limit.
        # People and publications get a type boost: «кто эксперт по теме» must
        # not lose them to densely-connected material nodes (audit gap).
        type_boost = {"person": 1000, "publication": 500, "team": 500, "laboratory": 500}

        def rank_key(node: str) -> int:
            data = graph.nodes[node]
            boost = type_boost.get(str(data.get("entity_type", "")), 0)
            return -(int(data.get("evidence_count", 0)) + boost)

        ranked = sorted((node for node in nodes if node != entity_id), key=rank_key)
        kept = {entity_id, *ranked[: max(0, limit - 1)]}
        subgraph = graph.subgraph(kept)
        return {
            "focus_entity_id": entity_id,
            "nodes": [
                {
                    "entity_id": node,
                    "entity_type": data.get("entity_type", "unknown"),
                    "label": data.get("label", node),
                    "evidence_count": int(data.get("evidence_count", 0)),
                }
                for node, data in subgraph.nodes(data=True)
            ],
            "edges": [
                {
                    "relation_id": key,
                    "source": src,
                    "target": dst,
                    "relation_type": data.get("relation_type", "RELATED"),
                    "evidence_count": int(data.get("evidence_count", 0)),
                }
                for src, dst, key, data in subgraph.edges(keys=True, data=True)
            ],
        }
