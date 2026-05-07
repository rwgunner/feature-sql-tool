from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set, Tuple

from sqlglot import exp

from feature_sql_tool.lineage.expression_expander import ExpressionExpander
from feature_sql_tool.models.graph import DependencyEdge, DependencyNode
from feature_sql_tool.scope.passthrough_detector import PassthroughDetector
from feature_sql_tool.scope.scope_registry import ScopeRegistry


@dataclass
class ColumnResolutionResult:
    resolved_kind: str
    source_nodes: List[DependencyNode] = field(default_factory=list)
    intermediate_nodes: List[DependencyNode] = field(default_factory=list)
    unresolved_nodes: List[DependencyNode] = field(default_factory=list)
    edges: List[DependencyEdge] = field(default_factory=list)
    terminal_node_ids: List[str] = field(default_factory=list)

    def merge(self, other: 'ColumnResolutionResult') -> None:
        self.source_nodes.extend(other.source_nodes)
        self.intermediate_nodes.extend(other.intermediate_nodes)
        self.unresolved_nodes.extend(other.unresolved_nodes)
        self.edges.extend(other.edges)
        self.terminal_node_ids.extend(other.terminal_node_ids)


class ColumnResolver:
    def __init__(self, scope_registry: ScopeRegistry) -> None:
        self.scope_registry = scope_registry
        self.expander = ExpressionExpander()
        self.passthrough_detector = PassthroughDetector()

    def resolve_column(self, scope_name: str, column: exp.Column) -> ColumnResolutionResult:
        return self._resolve_column(scope_name, column, visited=set())

    def _resolve_column(self, scope_name: str, column: exp.Column, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        if hasattr(self.scope_registry, 'has_scope') and not self.scope_registry.has_scope(scope_name):
            return self._make_unresolved(scope_name, column)

        key = (scope_name, column.name, column.table)
        if key in visited:
            return self._make_unresolved(scope_name, column)
        visited = set(visited)
        visited.add(key)

        alias_ref = self.scope_registry.find_alias(scope_name, column.name)
        if column.table is None and alias_ref is not None:
            return self._resolve_alias_expression(scope_name, alias_ref, visited)

        if column.table:
            relation = self.scope_registry.find_relation(scope_name, column.table)
            if relation is not None:
                if relation.relation_type == 'physical_table':
                    return self._make_source(relation.physical_table_name or column.table, column.name, scope_name)
                if relation.source_scope_name:
                    return self._resolve_relation_output_column(relation.source_scope_name, column.name, visited)
            fallback = self._resolve_via_scope_runtime(scope_name, column.table, column.name, visited)
            if fallback.resolved_kind != 'unresolved':
                return fallback

        return self._resolve_output_column(scope_name, column.name, visited)

    def _resolve_output_column(self, scope_name: str, column_name: str, visited: Set[Tuple[str, str, str | None]], require_declared_output: bool = False) -> ColumnResolutionResult:
        alias_ref = self.scope_registry.find_alias(scope_name, column_name)
        if alias_ref is not None:
            return self._resolve_alias_expression(scope_name, alias_ref, visited)

        set_descriptor = self.scope_registry.get_set_operation(scope_name)
        if set_descriptor is not None:
            return self._resolve_set_operation_output(scope_name, column_name, visited)

        if require_declared_output:
            return self._make_unresolved(scope_name, exp.column(column_name))

        relations = self.scope_registry.list_relations(scope_name)
        candidate_results: List[ColumnResolutionResult] = []
        for relation in relations:
            if relation.relation_type == 'physical_table':
                candidate_results.append(self._make_source(relation.physical_table_name or relation.relation_name, column_name, scope_name))
            elif relation.source_scope_name:
                candidate_results.append(self._resolve_relation_output_column(relation.source_scope_name, column_name, visited))

        candidate_results = [result for result in candidate_results if result.resolved_kind != 'unresolved']
        if len(candidate_results) == 1:
            return candidate_results[0]
        if len(candidate_results) > 1:
            return self._merge_candidates(scope_name, column_name, candidate_results)

        unresolved_column = exp.column(column_name)
        return self._make_unresolved(scope_name, unresolved_column)

    def _resolve_relation_output_column(self, source_scope_name: str, column_name: str, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        # When a column is referenced through a CTE/subquery relation, resolve only
        # columns that are actually declared by that relation's SELECT output.
        # Without this guard, an intermediate alias missing from the relation output
        # could be incorrectly treated as a physical source column of an upstream
        # table just because that relation ultimately reads from one table.
        return self._resolve_output_column(source_scope_name, column_name, visited, require_declared_output=True)

    def _resolve_set_operation_output(self, scope_name: str, column_name: str, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        descriptor = self.scope_registry.get_set_operation(scope_name)
        if descriptor is None:
            return self._make_unresolved(scope_name, exp.column(column_name))

        try:
            position = list(descriptor.output_columns).index(column_name)
        except ValueError:
            return self._make_unresolved(scope_name, exp.column(column_name))

        branch_specs = (
            (descriptor.left_scope_name, descriptor.left_output_expressions, descriptor.left_expression),
            (descriptor.right_scope_name, descriptor.right_output_expressions, descriptor.right_expression),
        )
        return self._resolve_set_position_from_branches(
            scope_name=scope_name,
            column_name=column_name,
            position=position,
            branch_specs=branch_specs,
            visited=visited,
        )

    def _resolve_set_position_from_branches(
        self,
        scope_name: str,
        column_name: str,
        position: int,
        branch_specs,
        visited: Set[Tuple[str, str, str | None]],
    ) -> ColumnResolutionResult:
        candidate_results: list[ColumnResolutionResult] = []
        for branch_scope_name, branch_outputs, branch_expression in branch_specs:
            if position >= len(branch_outputs):
                continue
            # Prefer direct resolution from the concrete branch SQL expression to
            # avoid asymmetric scope matching between UNION branches. Fall back to
            # scope-based resolution only if the direct branch resolve fails.
            branch_result = self._resolve_branch_expression(
                None,
                branch_outputs[position],
                visited,
                branch_expression=branch_expression,
                position=position,
            )
            if branch_result.resolved_kind == 'unresolved' and branch_scope_name is not None:
                branch_result = self._resolve_branch_expression(
                    branch_scope_name,
                    branch_outputs[position],
                    visited,
                    branch_expression=branch_expression,
                    position=position,
                )
            if branch_result.resolved_kind != 'unresolved':
                candidate_results.append(branch_result)

        if not candidate_results:
            return self._make_unresolved(scope_name, exp.column(column_name))
        if len(candidate_results) == 1:
            return candidate_results[0]

        merged = self._merge_candidates(scope_name, column_name, candidate_results, dependency_type='set', clause_type='union')
        if merged.resolved_kind == 'source_column' and len(candidate_results) > 1:
            merged.resolved_kind = 'set_output'
        return merged

    def _extract_set_expression(self, expression):
        if isinstance(expression, exp.SetOperation):
            return expression
        this_expr = getattr(expression, 'this', None)
        if isinstance(this_expr, exp.SetOperation):
            return this_expr
        return None

    def _extract_output_columns_from_expression(self, expression) -> list[str]:
        set_expression = self._extract_set_expression(expression)
        if set_expression is not None:
            return self._extract_output_columns_from_expression(getattr(set_expression, 'left', None))
        select_items = getattr(expression, 'expressions', []) or []
        output_columns: list[str] = []
        for idx, item in enumerate(select_items):
            alias_name = getattr(item, 'alias_or_name', None)
            if alias_name:
                output_columns.append(alias_name)
            elif isinstance(item, exp.Column):
                output_columns.append(item.name)
            else:
                output_columns.append(f'__col_{idx}')
        return output_columns

    def _extract_output_expressions_from_expression(self, expression) -> list:
        set_expression = self._extract_set_expression(expression)
        if set_expression is not None:
            return self._extract_output_expressions_from_expression(getattr(set_expression, 'left', None))
        select_items = getattr(expression, 'expressions', []) or []
        return [item.this if isinstance(item, exp.Alias) else item for item in select_items]

    def _resolve_set_expression_output(self, set_expression, column_name: str, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        output_columns = self._extract_output_columns_from_expression(set_expression)
        try:
            position = output_columns.index(column_name)
        except ValueError:
            return self._make_unresolved('__set_branch__', exp.column(column_name))
        branch_specs = (
            (None, tuple(self._extract_output_expressions_from_expression(getattr(set_expression, 'left', None))), getattr(set_expression, 'left', None)),
            (None, tuple(self._extract_output_expressions_from_expression(getattr(set_expression, 'right', None))), getattr(set_expression, 'right', None)),
        )
        return self._resolve_set_position_from_branches(
            scope_name='__set_branch__',
            column_name=column_name,
            position=position,
            branch_specs=branch_specs,
            visited=visited,
        )

    def _resolve_output_position(self, scope_name: str, position: int, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        set_descriptor = self.scope_registry.get_set_operation(scope_name)
        if set_descriptor is not None:
            if position >= len(set_descriptor.output_columns):
                return self._make_unresolved(scope_name, exp.column(f'__col_{position}'))
            return self._resolve_set_operation_output(scope_name, set_descriptor.output_columns[position], visited)

        scope_record = self.scope_registry.get_scope(scope_name)
        expression = scope_record.expression
        select_items = getattr(expression, 'expressions', []) or []
        if position >= len(select_items):
            return self._make_unresolved(scope_name, exp.column(f'__col_{position}'))
        item = select_items[position]
        expr = item.this if isinstance(item, exp.Alias) else item
        return self._resolve_branch_expression(scope_name, expr, visited, position=position, branch_expression=expression)

    def _resolve_branch_expression(self, scope_name: str | None, expr, visited: Set[Tuple[str, str, str | None]], branch_expression=None, position: int | None = None) -> ColumnResolutionResult:
        passthrough_column = self.passthrough_detector.extract_passthrough_column(expr)
        if passthrough_column is not None:
            if scope_name is not None:
                return self._resolve_passthrough_alias(scope_name, passthrough_column.copy(), visited)
            return self._resolve_column_from_branch_expression(branch_expression, passthrough_column.copy(), visited)

        if isinstance(expr, exp.Column):
            if scope_name is not None:
                return self._resolve_column(scope_name, expr.copy(), visited)
            return self._resolve_column_from_branch_expression(branch_expression, expr.copy(), visited)

        synthetic_alias_name = getattr(expr, 'alias_or_name', None) or (f'__pos_{position}' if position is not None else '__expr')
        synthetic_sql = expr.sql()

        # Expressions that come from an anonymous UNION/UNION ALL branch are
        # implementation details of set-operation resolution, not user-facing
        # intermediate features. Resolve their upstream source columns directly
        # and let the parent set_output node represent the UNION output. This
        # prevents artifacts such as int:__set_branch__:__pos_3 from leaking into
        # intermediate_features / filter_only_intermediate_features.
        if scope_name is None:
            result = ColumnResolutionResult(resolved_kind='source_column')
            for inner_column in self.expander.collect_columns(expr):
                inner_result = self._resolve_column_from_branch_expression(branch_expression, inner_column.copy(), visited)
                result.merge(inner_result)
            if result.source_nodes or result.intermediate_nodes:
                result.resolved_kind = 'source_column'
                return result
            return self._make_unresolved('__set_branch__', exp.column(synthetic_alias_name))

        synthetic_scope_name = scope_name
        node_id = f"int:{synthetic_scope_name}:{synthetic_alias_name}"
        intermediate = DependencyNode(
            node_id=node_id,
            node_type='intermediate_feature',
            name=synthetic_alias_name,
            scope_name=synthetic_scope_name,
            expression_sql=synthetic_sql,
        )
        result = ColumnResolutionResult(
            resolved_kind='intermediate_feature',
            intermediate_nodes=[intermediate],
            terminal_node_ids=[node_id],
        )
        for inner_column in self.expander.collect_columns(expr):
            inner_result = self._resolve_column(scope_name, inner_column.copy(), visited)
            result.merge(inner_result)
            for terminal_id in inner_result.terminal_node_ids:
                result.edges.append(
                    DependencyEdge(
                        from_node=terminal_id,
                        to_node=node_id,
                        dependency_type='value',
                        clause_type='select',
                        scope_name=synthetic_scope_name,
                        expression_sql=synthetic_sql,
                    )
                )
        return result

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
        if passthrough_column.table:
            return self._resolve_column(scope_name, passthrough_column.copy(), visited)
        return self._resolve_output_column_through_relations(scope_name, passthrough_column.name, visited)

    def _resolve_output_column_through_relations(self, scope_name: str, column_name: str, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        set_descriptor = self.scope_registry.get_set_operation(scope_name)
        if set_descriptor is not None:
            return self._resolve_set_operation_output(scope_name, column_name, visited)

        relations = self.scope_registry.list_relations(scope_name)
        candidate_results: List[ColumnResolutionResult] = []
        for relation in relations:
            if relation.relation_type == 'physical_table':
                candidate_results.append(self._make_source(relation.physical_table_name or relation.relation_name, column_name, scope_name))
            elif relation.source_scope_name:
                candidate_results.append(self._resolve_relation_output_column(relation.source_scope_name, column_name, visited))

        candidate_results = [result for result in candidate_results if result.resolved_kind != 'unresolved']
        if len(candidate_results) == 1:
            return candidate_results[0]
        if len(candidate_results) > 1:
            return self._merge_candidates(scope_name, column_name, candidate_results)

        return self._make_unresolved(scope_name, exp.column(column_name))

    def _resolve_via_scope_runtime(self, scope_name: str, relation_alias: str, column_name: str, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        scope_record = self.scope_registry.get_scope(scope_name)
        scope_obj = scope_record.scope_obj

        for mapping_name in ('selected_sources', 'sources'):
            mapping = getattr(scope_obj, mapping_name, None) or {}
            if mapping_name == 'selected_sources':
                iterator = ((alias, value[1]) for alias, value in mapping.items())
            else:
                iterator = mapping.items()
            for alias, source_obj in iterator:
                if alias != relation_alias:
                    continue
                source_scope_name = self.scope_registry.find_scope_name_for_obj(source_obj)
                if source_scope_name:
                    return self._resolve_relation_output_column(source_scope_name, column_name, visited)
                if isinstance(source_obj, exp.Table):
                    return self._make_source(source_obj.name, column_name, scope_name)

        expression = scope_record.expression
        if expression is not None:
            for table in expression.find_all(exp.Table):
                alias_or_name = table.alias_or_name or table.name
                if alias_or_name == relation_alias:
                    return self._make_source(table.name, column_name, scope_name)

        return self._make_unresolved(scope_name, exp.column(column_name, table=relation_alias))

    def _resolve_column_from_branch_expression(self, branch_expression, column: exp.Column, visited: Set[Tuple[str, str, str | None]]) -> ColumnResolutionResult:
        if branch_expression is None:
            return self._make_unresolved('__set_branch__', column)

        set_expression = self._extract_set_expression(branch_expression)
        if set_expression is not None and column.table is None:
            return self._resolve_set_expression_output(set_expression, column.name, visited)

        # If column is unqualified, try to resolve by output alias/passthrough within the branch select itself.
        select_items = getattr(branch_expression, 'expressions', []) or []
        if column.table is None:
            for item in select_items:
                alias_name = getattr(item, 'alias_or_name', None)
                if alias_name != column.name:
                    continue
                expr = item.this if isinstance(item, exp.Alias) else item
                return self._resolve_branch_expression(None, expr, visited, branch_expression=branch_expression)

        if column.table:
            for table in branch_expression.find_all(exp.Table):
                alias_or_name = table.alias_or_name or table.name
                if alias_or_name == column.table:
                    return self._make_source(table.name, column.name, '__set_branch__')

        # Fallback: if there is exactly one physical table in the branch, resolve to it.
        tables = list(branch_expression.find_all(exp.Table))
        unique_tables = []
        seen = set()
        for table in tables:
            if table.name not in seen:
                seen.add(table.name)
                unique_tables.append(table)
        if len(unique_tables) == 1:
            return self._make_source(unique_tables[0].name, column.name, '__set_branch__')

        return self._make_unresolved('__set_branch__', column)

    def _merge_candidates(self, scope_name: str, column_name: str, results: list[ColumnResolutionResult], dependency_type: str = 'passthrough', clause_type: str = 'select') -> ColumnResolutionResult:
        synthetic_node_id = f"set:{scope_name}:{column_name}:{dependency_type}"
        synthetic_node = DependencyNode(
            node_id=synthetic_node_id,
            node_type='set_output' if dependency_type == 'set' else 'relation_output',
            name=column_name,
            scope_name=scope_name,
            expression_sql=column_name,
        )
        merged = ColumnResolutionResult(
            resolved_kind='intermediate_feature',
            intermediate_nodes=[synthetic_node],
            terminal_node_ids=[synthetic_node_id],
        )
        for result in results:
            merged.merge(result)
            for terminal_id in result.terminal_node_ids:
                merged.edges.append(
                    DependencyEdge(
                        from_node=terminal_id,
                        to_node=synthetic_node_id,
                        dependency_type=dependency_type,
                        clause_type=clause_type,
                        scope_name=scope_name,
                        expression_sql=column_name,
                    )
                )
        return merged

    def _make_source(self, table_name: str, column_name: str, scope_name: str) -> ColumnResolutionResult:
        normalized_table_name = table_name.split(' AS ')[0].strip() if table_name else table_name
        node = DependencyNode(
            node_id=f"src:{normalized_table_name}.{column_name}",
            node_type='source_column',
            name=f"{normalized_table_name}.{column_name}",
            scope_name=scope_name,
            source_table=normalized_table_name,
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
            node_id=f"unresolved:{table_name}.{column_name}",
            node_type='unresolved_column',
            name=f"{table_name}.{column_name}",
            scope_name=scope_name,
            source_table=table_name,
            source_column=column_name,
        )
        return ColumnResolutionResult(
            resolved_kind='unresolved',
            unresolved_nodes=[node],
            terminal_node_ids=[node.node_id],
        )
