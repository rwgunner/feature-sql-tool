from __future__ import annotations

from feature_sql_tool.models.graph import DependencyNode


class NodeCanonicalizer:
    def canonical_key(self, node: DependencyNode) -> tuple:
        if node.node_type == 'source_column':
            return (node.node_type, node.source_table, node.source_column)
        if node.node_type in {'intermediate_feature', 'aggregate_feature'}:
            return (node.node_type, node.expression_sql, node.grain)
        return (node.node_type, node.node_id)
