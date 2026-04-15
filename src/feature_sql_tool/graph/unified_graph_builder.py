from __future__ import annotations

from dataclasses import dataclass

from feature_sql_tool.graph.canonicalizer import NodeCanonicalizer
from feature_sql_tool.models.graph import DependencyEdge, DependencyNode
from feature_sql_tool.models.lineage_result import FeatureLineageResult


@dataclass
class UnifiedFeatureGraph:
    nodes: dict[str, DependencyNode]
    edges: list[DependencyEdge]
    feature_to_final_node: dict[str, str]
    node_id_mapping: dict[str, str]


class UnifiedFeatureGraphBuilder:
    def __init__(self) -> None:
        self.canonicalizer = NodeCanonicalizer()

    def build(self, results: list[FeatureLineageResult]) -> UnifiedFeatureGraph:
        canonical_to_node_id: dict[tuple, str] = {}
        nodes: dict[str, DependencyNode] = {}
        edges: list[DependencyEdge] = []
        edge_keys = set()
        feature_to_final_node: dict[str, str] = {}
        node_id_mapping: dict[str, str] = {}

        for result in results:
            local_map: dict[str, str] = {}
            for node_id, node in result.nodes.items():
                if node.node_type == 'final_feature':
                    target_id = node_id
                else:
                    key = self.canonicalizer.canonical_key(node)
                    target_id = canonical_to_node_id.get(key, node_id)
                    canonical_to_node_id.setdefault(key, target_id)
                nodes[target_id] = node if target_id == node_id else nodes.get(target_id, node)
                local_map[node_id] = target_id
                node_id_mapping[node_id] = target_id

            for edge in result.edges:
                remapped = DependencyEdge(
                    from_node=local_map[edge.from_node],
                    to_node=local_map[edge.to_node],
                    dependency_type=edge.dependency_type,
                    clause_type=edge.clause_type,
                    scope_name=edge.scope_name,
                    expression_sql=edge.expression_sql,
                )
                edge_key = (
                    remapped.from_node,
                    remapped.to_node,
                    remapped.dependency_type,
                    remapped.clause_type,
                    remapped.scope_name,
                    remapped.expression_sql,
                )
                if edge_key not in edge_keys:
                    edge_keys.add(edge_key)
                    edges.append(remapped)

            feature_to_final_node[result.feature_spec.feature_name] = local_map[f"fin:{result.feature_spec.feature_name}"]

        return UnifiedFeatureGraph(
            nodes=nodes,
            edges=edges,
            feature_to_final_node=feature_to_final_node,
            node_id_mapping=node_id_mapping,
        )
