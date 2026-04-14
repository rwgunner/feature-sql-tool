from __future__ import annotations

from feature_sql_tool.models.graph import DependencyNode


class NodeCanonicalizer:
    def canonical_key(self, node: DependencyNode) -> tuple:
        return (
            node.node_type,
            node.name,
            node.expression_sql,
            node.source_table,
            node.source_column,
        )
