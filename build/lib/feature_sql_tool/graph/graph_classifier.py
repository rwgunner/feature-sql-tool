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

    def classify_unresolved_columns(self, graph: DependencyGraph) -> list[str]:
        return sorted(
            node_id
            for node_id, node in graph.nodes.items()
            if node.node_type == 'unresolved_column'
        )

    def classify_source_columns_by_role(self, graph: DependencyGraph, final_node_id: str) -> dict[str, list[str]]:
        roles = {
            'value': [],
            'filter': [],
            'join': [],
            'group': [],
        }

        source_nodes = [node_id for node_id, node in graph.nodes.items() if node.node_type == 'source_column']
        for node_id in source_nodes:
            if graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'group'}, {'value'}):
                roles['value'].append(node_id)
            if graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'filter', 'join'}, {'filter'}):
                roles['filter'].append(node_id)
            if graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'join'}, {'join'}):
                roles['join'].append(node_id)
            if graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'group'}, {'group'}):
                roles['group'].append(node_id)

        return {key: sorted(set(values)) for key, values in roles.items()}
