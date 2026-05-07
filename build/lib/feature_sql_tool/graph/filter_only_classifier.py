from __future__ import annotations

from feature_sql_tool.graph.dependency_graph import DependencyGraph
from feature_sql_tool.graph.node_filters import is_synthetic_intermediate_feature


class FilterOnlyClassifier:
    def classify(self, graph: DependencyGraph, final_node_id: str) -> list[str]:
        result: list[str] = []
        for node_id, node in graph.nodes.items():
            if node.node_type != 'intermediate_feature' or is_synthetic_intermediate_feature(node):
                continue
            has_filter_path = graph.path_exists(node_id, final_node_id, {'filter', 'join', 'passthrough', 'set'})
            has_value_path = graph.path_exists(node_id, final_node_id, {'value', 'group', 'passthrough', 'set'})
            if has_filter_path and not has_value_path:
                result.append(node_id)
        return sorted(result)
