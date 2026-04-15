from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set, Tuple

from sqlglot import exp

from feature_sql_tool.lineage.expression_expander import ExpressionExpander
from feature_sql_tool.models.graph import DependencyEdge, DependencyNode
from feature_sql_tool.scope.scope_registry import ScopeRegistry


@dataclass
class ColumnResolutionResult:
    resolved_kind: str
    source_nodes: List[DependencyNode] = field(default_factory=list)
    intermediate_nodes: List[DependencyNode] = field(default_factory=list)
    edges: List[DependencyEdge] = field(default_factory=list)
    terminal_node_ids: List[str] = field(default_factory=list)

    def merge(self, other: 'ColumnResolutionResult') -> None:
        self.source_nodes.extend(other.source_nodes)
        self.intermediate_nodes.extend(other.intermediate_nodes)
        self.edges.extend(other.edges)
        self.terminal_node_ids.extend(other.terminal_node_ids)


class ColumnResolver:
    def __init__(self, scope_registry: ScopeRegistry) -> None:
        self.scope_registry = scope_registry
        self.expander = ExpressionExpander()

    def resolve_column(self, scope_name: str, column: exp.Column) -> ColumnResolutionResult:
        return self._resolve_column(scope_name, column, visited=set())

    def _resolve_column(self, scope_name: str, column: exp.Column, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        key = (scope_name, column.sql(), column.table)
        if key in visited:
            return self._make_unresolved(scope_name, column)
        visited = set(visited)
        visited.add(key)

        # 1. Alias defined in current scope SELECT list.
        alias_ref = self.scope_registry.find_alias(scope_name, column.name)
        if column.table is None and alias_ref is not None:
            return self._resolve_alias_expression(scope_name, alias_ref, visited)

        # 2. Relation-qualified resolution.
        if column.table:
            relation = self.scope_registry.find_relation(scope_name, column.table)
            if relation is not None:
                if relation.relation_type == 'physical_table':
                    return self._make_source(relation.physical_table_name or column.table, column.name, scope_name)
                if relation.source_scope_name:
                    return self._resolve_output_column(relation.source_scope_name, column.name, visited)

        # 3. Unqualified column: resolve through a single source when safe.
        relations = self.scope_registry.list_relations(scope_name)
        if len(relations) == 1:
            relation = relations[0]
            if relation.relation_type == 'physical_table':
                return self._make_source(relation.physical_table_name or relation.relation_name, column.name, scope_name)
            if relation.source_scope_name:
                return self._resolve_output_column(relation.source_scope_name, column.name, visited)

        # 4. Try to find matching alias downstream in source scopes; only accept unique resolution.
        candidate_results: List[ColumnResolutionResult] = []
        for relation in relations:
            if relation.source_scope_name:
                source_scope_name = relation.source_scope_name
                if self.scope_registry.find_alias(source_scope_name, column.name) is not None:
                    candidate_results.append(self._resolve_output_column(source_scope_name, column.name, visited))
        if len(candidate_results) == 1:
            return candidate_results[0]

        return self._make_unresolved(scope_name, column)

    def _resolve_output_column(self, scope_name: str, column_name: str, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        alias_ref = self.scope_registry.find_alias(scope_name, column_name)
        if alias_ref is not None:
            return self._resolve_alias_expression(scope_name, alias_ref, visited)

        relations = self.scope_registry.list_relations(scope_name)
        if len(relations) == 1:
            relation = relations[0]
            if relation.relation_type == 'physical_table':
                return self._make_source(relation.physical_table_name or relation.relation_name, column_name, scope_name)
            if relation.source_scope_name:
                return self._resolve_output_column(relation.source_scope_name, column_name, visited)

        unresolved_column = exp.column(column_name)
        return self._make_unresolved(scope_name, unresolved_column)

    def _resolve_alias_expression(self, scope_name, alias_ref, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        if alias_ref.is_passthrough and alias_ref.passthrough_column is not None:
            return self._resolve_passthrough_alias(scope_name, alias_ref.passthrough_column.copy(), visited)

        node_id = f"int:{scope_name}:{alias_ref.alias_name}"
        intermediate = DependencyNode(
            node_id=node_id,
            node_type='intermediate_feature',
            name=alias_ref.alias_name,
            scope_name=scope_name,
            expression_sql=alias_ref.expression_sql,
        )
        result = ColumnResolutionResult(
            resolved_kind='intermediate_feature',
            intermediate_nodes=[intermediate],
            terminal_node_ids=[node_id],
        )
        for inner_column in self.expander.collect_columns(alias_ref.expression):
            inner_result = self._resolve_column(scope_name, inner_column.copy(), visited)
            result.merge(inner_result)
            for terminal_id in inner_result.terminal_node_ids:
                result.edges.append(
                    DependencyEdge(
                        from_node=terminal_id,
                        to_node=node_id,
                        dependency_type='value',
                        clause_type='select',
                        scope_name=scope_name,
                        expression_sql=alias_ref.expression_sql,
                    )
                )
        return result

    def _resolve_passthrough_alias(self, scope_name: str, passthrough_column: exp.Column, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        # Qualified passthrough columns can be resolved normally because they target an explicit relation.
        if passthrough_column.table:
            return self._resolve_column(scope_name, passthrough_column, visited)

        # For unqualified passthrough columns, do not recurse into the same alias again.
        # Instead, propagate the column through upstream relations / source scopes.
        relations = self.scope_registry.list_relations(scope_name)
        if len(relations) == 1:
            relation = relations[0]
            if relation.relation_type == 'physical_table':
                return self._make_source(relation.physical_table_name or relation.relation_name, passthrough_column.name, scope_name)
            if relation.source_scope_name:
                return self._resolve_output_column(relation.source_scope_name, passthrough_column.name, visited)

        candidate_results: List[ColumnResolutionResult] = []
        for relation in relations:
            if relation.source_scope_name:
                candidate_results.append(self._resolve_output_column(relation.source_scope_name, passthrough_column.name, visited))
        if len(candidate_results) == 1:
            return candidate_results[0]

        return self._make_unresolved(scope_name, passthrough_column)

    def _make_source(self, table_name: str, column_name: str, scope_name: str) -> ColumnResolutionResult:
        node = DependencyNode(
            node_id=f"src:{table_name}.{column_name}",
            node_type='source_column',
            name=f"{table_name}.{column_name}",
            scope_name=scope_name,
            source_table=table_name,
            source_column=column_name,
        )
        return ColumnResolutionResult(
            resolved_kind='source_column',
            source_nodes=[node],
            terminal_node_ids=[node.node_id],
        )

    def _make_unresolved(self, scope_name: str, column: exp.Column) -> ColumnResolutionResult:
        table_name = column.table or '__unresolved__'
        column_name = column.name
        node = DependencyNode(
            node_id=f"src:{table_name}.{column_name}",
            node_type='source_column',
            name=f"{table_name}.{column_name}",
            scope_name=scope_name,
            source_table=table_name,
            source_column=column_name,
        )
        return ColumnResolutionResult(
            resolved_kind='unresolved',
            source_nodes=[node],
            terminal_node_ids=[node.node_id],
        )
