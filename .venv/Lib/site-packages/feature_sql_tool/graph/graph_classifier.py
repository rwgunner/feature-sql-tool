from __future__ import annotations

from feature_sql_tool.graph.dependency_graph import DependencyGraph


class GraphClassifier:
    def classify_source_columns(self, graph: DependencyGraph) -> list[str]:
        return sorted(
            node_id
            for node_id, node in graph.nodes.items()
            if node.node_type == 'source_column'
        )

    def classify_intermediate_features(self, graph: DependencyGraph) -> list[str]:
        return sorted(
            node_id
            for node_id, node in graph.nodes.items()
            if node.node_type == 'intermediate_feature'
        )
