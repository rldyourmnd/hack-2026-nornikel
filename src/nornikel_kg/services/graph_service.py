from __future__ import annotations

from typing import Any

import networkx as nx

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository


class GraphService:
    """Graph neighborhood over the DuckDB entity/relation layer.

    `neighborhood()` uses depth-limited indexed SQL traversal (no full-graph
    materialization). `build_graph()` remains as a dev/analysis utility that
    materializes the whole graph into NetworkX — it is NOT on the request path.
    """

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
        # Depth-limited SQL traversal (no full-graph materialization); the
        # ranking and response shape below are preserved exactly.
        result = self.repository.graph_neighborhood(entity_id, depth=depth, limit=limit)
        if result is None:
            return None
        nodes_by_id = {node["entity_id"]: node for node in result["nodes"]}
        # People and publications get a type boost: «кто эксперт по теме» must
        # not lose them to densely-connected material nodes.
        type_boost = {"person": 1000, "publication": 500, "team": 500, "laboratory": 500}

        def rank_key(node_id: str) -> int:
            data = nodes_by_id[node_id]
            boost = type_boost.get(str(data.get("entity_type", "")), 0)
            return -(int(data.get("evidence_count", 0)) + boost)

        neighbor_ids = sorted(
            (node_id for node_id in nodes_by_id if node_id != entity_id), key=rank_key
        )
        kept_ids = [entity_id, *neighbor_ids[: max(0, limit - 1)]]
        kept = set(kept_ids)
        return {
            "focus_entity_id": entity_id,
            "nodes": [
                {
                    "entity_id": node_id,
                    "entity_type": nodes_by_id[node_id].get("entity_type", "unknown"),
                    "label": nodes_by_id[node_id].get("canonical_name", node_id),
                    "evidence_count": int(nodes_by_id[node_id].get("evidence_count", 0)),
                }
                for node_id in kept_ids
                if node_id in nodes_by_id
            ],
            "edges": [
                {
                    "relation_id": edge["relation_id"],
                    "source": edge["src_entity_id"],
                    "target": edge["dst_entity_id"],
                    "relation_type": edge.get("relation_type", "RELATED"),
                    "evidence_count": int(edge.get("evidence_count", 0)),
                }
                for edge in result["edges"]
                if edge["src_entity_id"] in kept and edge["dst_entity_id"] in kept
            ],
        }
