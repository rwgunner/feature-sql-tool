from __future__ import annotations

from feature_sql_tool.graph.dependency_graph import DependencyGraph
from feature_sql_tool.graph.node_filters import is_synthetic_intermediate_feature


class GraphClassifier:
    def classify_source_columns(self, graph: DependencyGraph) -> list[str]:
        return sorted(node_id for node_id, node in graph.nodes.items() if node.node_type == 'source_column')

    def classify_intermediate_features(self, graph: DependencyGraph) -> list[str]:
        return sorted(
            node_id
            for node_id, node in graph.nodes.items()
            if node.node_type == 'intermediate_feature' and not is_synthetic_intermediate_feature(node)
        )

    def classify_unresolved_columns(self, graph: DependencyGraph) -> list[str]:
        return sorted(node_id for node_id, node in graph.nodes.items() if node.node_type == 'unresolved_column')

    def classify_source_columns_by_role(self, graph: DependencyGraph, final_node_id: str) -> dict[str, list[str]]:
        roles = {'value': [], 'filter': [], 'join': [], 'group': []}

        source_nodes = [node_id for node_id, node in graph.nodes.items() if node.node_type == 'source_column']
        for node_id in source_nodes:
            if graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'group', 'passthrough', 'set'}, {'value'}):
                roles['value'].append(node_id)
            if graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'filter', 'join', 'group', 'passthrough', 'set'}, {'filter'}):
                roles['filter'].append(node_id)
            if graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'join', 'group', 'passthrough', 'set'}, {'join'}):
                roles['join'].append(node_id)
            if graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'group', 'passthrough', 'set'}, {'group'}):
                roles['group'].append(node_id)

        # UNION/set-operation bugfix: if a set_output node participates in a value path to the final
        # feature, then all upstream source columns feeding that set_output should also be considered
        # value sources. This preserves symmetry across both UNION branches even when only one branch
        # receives a direct value-edge during graph construction.
        for node_id, node in graph.nodes.items():
            if node.node_type != 'set_output':
                continue
            if not graph.path_exists_with_required_types(node_id, final_node_id, {'value', 'group', 'passthrough', 'set'}, {'value'}):
                continue
            upstream = graph.reachable_upstream(node_id, {'set', 'passthrough', 'value'})
            for upstream_node_id in upstream:
                upstream_node = graph.nodes.get(upstream_node_id)
                if upstream_node is not None and upstream_node.node_type == 'source_column':
                    roles['value'].append(upstream_node_id)

        return {key: sorted(set(values)) for key, values in roles.items()}
