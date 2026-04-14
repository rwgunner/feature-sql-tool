from __future__ import annotations

from typing import Iterable

from feature_sql_tool.models.graph import DependencyEdge, DependencyNode
from feature_sql_tool.models.lineage_result import FeatureLineageResult


class FeatureGraphMerger:
    def merge(
        self, results: Iterable[FeatureLineageResult]
    ) -> tuple[dict[str, DependencyNode], list[DependencyEdge]]:
        nodes: dict[str, DependencyNode] = {}
        edges: list[DependencyEdge] = []

        for result in results:
            for node_id, node in result.nodes.items():
                nodes[node_id] = node
            edges.extend(result.edges)

        return nodes, edges
