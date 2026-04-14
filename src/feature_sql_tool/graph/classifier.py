from __future__ import annotations

from typing import List

from feature_sql_tool.graph.dependency_graph import DependencyGraph


class GraphClassifier:
    def classify_source_columns(self, graph: DependencyGraph) -> List[str]:
        return sorted(
            node_id
            for node_id, node in graph.nodes.items()
            if node.node_type == "source_column"
        )

    def classify_intermediate_features(self, graph: DependencyGraph) -> List[str]:
        return sorted(
            node_id
            for node_id, node in graph.nodes.items()
            if node.node_type == "intermediate_feature"
        )

    def classify_filter_only_intermediate_features(self, graph: DependencyGraph) -> List[str]:
        """
        Draft version: intermediate features with only filter/join downstream edges.
        """
        result: List[str] = []

        for node_id, node in graph.nodes.items():
            if node.node_type != "intermediate_feature":
                continue

            downstream_edges = [e for e in graph.edges if e.from_node == node_id]
            if not downstream_edges:
                continue

            if all(e.dependency_type in {"filter", "join"} for e in downstream_edges):
                result.append(node_id)

        return sorted(result)
