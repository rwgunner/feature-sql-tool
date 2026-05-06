from __future__ import annotations

from sqlglot import exp, parse_one

from feature_sql_tool.graph.dependency_graph import DependencyGraph
from feature_sql_tool.graph.filter_only_classifier import FilterOnlyClassifier
from feature_sql_tool.graph.graph_classifier import GraphClassifier
from feature_sql_tool.lineage.column_resolver import ColumnResolver
from feature_sql_tool.lineage.expression_expander import ExpressionExpander
from feature_sql_tool.lineage.filter_dependency_collector import FilterDependencyCollector
from feature_sql_tool.models.graph import DependencyEdge, DependencyNode
from feature_sql_tool.models.lineage_result import FeatureLineageResult
from feature_sql_tool.parser.ast_normalizer import AstNormalizer
from feature_sql_tool.parser.sql_parser import SqlParser


class FeatureLineageExtractor:
    def __init__(self) -> None:
        self.sql_parser = SqlParser()
        self.expander = ExpressionExpander()
        self.classifier = GraphClassifier()
        self.filter_only = FilterOnlyClassifier()
        self.normalizer = AstNormalizer()

    def extract(self, feature_spec) -> FeatureLineageResult:
        parse_result = self.sql_parser.parse_feature(feature_spec)
        graph = DependencyGraph()
        scope_registry = parse_result.scope_registry
        root_scope_name = scope_registry.root_scope_name
        if root_scope_name is None:
            raise ValueError(f"No root scope found for feature '{feature_spec.feature_name}'")
        root_record = scope_registry.get_scope(root_scope_name)
        resolver = ColumnResolver(scope_registry)
        filter_collector = FilterDependencyCollector()

        self._validate_entity_keys_in_final_select(feature_spec.feature_name, root_record.expression, tuple(feature_spec.entity_keys or ()))

        final_expr_ref = scope_registry.find_alias(root_scope_name, feature_spec.feature_name)
        if final_expr_ref is None:
            final_expr = self._find_final_expression(root_record.expression, feature_spec.feature_name)
            if final_expr is None:
                raise ValueError(f"Final alias '{feature_spec.feature_name}' was not found in root scope for feature '{feature_spec.feature_name}'")
            final_expr_sql = self.normalizer.normalize_expression_sql(final_expr, feature_spec.dialect)
        else:
            final_expr = final_expr_ref.expression
            final_expr_sql = final_expr_ref.expression_sql

        final_node_id = f"fin:{feature_spec.feature_name}"
        graph.add_node(
            DependencyNode(
                node_id=final_node_id,
                node_type='final_feature',
                name=feature_spec.feature_name,
                scope_name=root_scope_name,
                expression_sql=final_expr_sql,
                grain=','.join(feature_spec.entity_keys or ()),
                feature_name=feature_spec.feature_name,
            )
        )

        for col in self.expander.collect_columns(final_expr):
            resolved = resolver.resolve_column(root_scope_name, col.copy())
            self._merge_resolution(graph, resolved)
            self._attach_resolution_context_edges(
                graph=graph,
                resolved=resolved,
                target_node_id=final_node_id,
                dependency_type='value',
                clause_type='select',
                scope_name=root_scope_name,
                expression_sql=str(col),
            )

        for scope_record in scope_registry.iter_scopes():
            for col in self._collect_entity_and_group_columns(scope_record.expression, list(feature_spec.entity_keys or (feature_spec.entity_key,))):
                resolved = resolver.resolve_column(scope_record.scope_name, col.copy())
                self._merge_resolution(graph, resolved)
                for terminal_id in resolved.terminal_node_ids:
                    graph.add_edge(DependencyEdge(from_node=terminal_id, to_node=final_node_id, dependency_type='group', clause_type='group_by', scope_name=scope_record.scope_name, expression_sql=str(col)))

            filters = filter_collector.collect(scope_record.expression)
            for clause_type, columns in filters.items():
                dependency_type = 'join' if clause_type == 'join_on' else 'filter'
                for col in columns:
                    resolved = resolver.resolve_column(scope_record.scope_name, col.copy())
                    self._merge_resolution(graph, resolved)
                    self._attach_resolution_context_edges(
                        graph=graph,
                        resolved=resolved,
                        target_node_id=final_node_id,
                        dependency_type=dependency_type,
                        clause_type=clause_type,
                        scope_name=scope_record.scope_name,
                        expression_sql=str(col),
                    )

        source_columns = self.classifier.classify_source_columns(graph)
        source_columns = self._finalize_source_columns(scope_registry, resolver, graph, source_columns, feature_spec.dialect)

        return FeatureLineageResult(
            feature_spec=feature_spec,
            nodes=graph.nodes,
            edges=graph.edges,
            source_columns=source_columns,
            intermediate_features=self.classifier.classify_intermediate_features(graph),
            filter_only_intermediate_features=self.filter_only.classify(graph, final_node_id),
            unresolved_columns=self.classifier.classify_unresolved_columns(graph),
        )

    def _merge_resolution(self, graph: DependencyGraph, resolved) -> None:
        for node in resolved.source_nodes + resolved.intermediate_nodes + resolved.unresolved_nodes:
            graph.add_node(node)
        for edge in resolved.edges:
            graph.add_edge(edge)

    def _find_final_expression(self, expression, final_alias: str):
        select_items = getattr(expression, 'expressions', []) or []
        for item in select_items:
            alias_or_name = getattr(item, 'alias_or_name', None)
            if alias_or_name == final_alias:
                return item.this if isinstance(item, exp.Alias) else item
        return None

    def _validate_entity_keys_in_final_select(self, feature_name: str, expression, entity_keys: tuple[str, ...]) -> None:
        select_items = getattr(expression, 'expressions', []) or []
        select_names = set()
        for item in select_items:
            alias_or_name = getattr(item, 'alias_or_name', None)
            if alias_or_name:
                select_names.add(alias_or_name)
            elif isinstance(item, exp.Column):
                select_names.add(item.name)
        missing = [key for key in entity_keys if key not in select_names]
        if missing:
            missing_fmt = ', '.join(repr(m) for m in missing)
            raise ValueError(f"Feature '{feature_name}': final SELECT does not contain entity key(s) {missing_fmt}")

    def _collect_entity_and_group_columns(self, expression, entity_keys: list[str]) -> list[exp.Column]:
        columns: list[exp.Column] = []
        seen: set[str] = set()

        group_clause = expression.args.get('group') if expression is not None else None
        if group_clause is not None:
            for col in group_clause.find_all(exp.Column):
                sql = col.sql()
                if sql not in seen:
                    seen.add(sql)
                    columns.append(col)

        select_items = getattr(expression, 'expressions', []) or []
        for item in select_items:
            alias_name = getattr(item, 'alias_or_name', None)
            if alias_name in entity_keys:
                expr = item.this if isinstance(item, exp.Alias) else item
                for col in self.expander.collect_columns(expr):
                    sql = col.sql()
                    if sql not in seen:
                        seen.add(sql)
                        columns.append(col)
                if isinstance(expr, exp.Column):
                    sql = expr.sql()
                    if sql not in seen:
                        seen.add(sql)
                        columns.append(expr)
        return columns
    def _attach_resolution_context_edges(self, graph: DependencyGraph, resolved, target_node_id: str, dependency_type: str, clause_type: str, scope_name: str, expression_sql: str | None) -> None:
        for terminal_id in resolved.terminal_node_ids:
            graph.add_edge(DependencyEdge(
                from_node=terminal_id,
                to_node=target_node_id,
                dependency_type=dependency_type,
                clause_type=clause_type,
                scope_name=scope_name,
                expression_sql=expression_sql,
            ))

        # For value-context through UNION/set outputs, also attach direct value edges
        # from all upstream source columns that feed the set/relation output. This
        # keeps both UNION branches visible to role classification even when one
        # branch only reaches the target through a synthetic set_output node.
        if dependency_type != 'value':
            return

        visited = set()
        stack = list(resolved.terminal_node_ids)
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            node = graph.nodes.get(node_id)
            if node is not None and node.node_type == 'source_column':
                graph.add_edge(DependencyEdge(
                    from_node=node_id,
                    to_node=target_node_id,
                    dependency_type='value',
                    clause_type=clause_type,
                    scope_name=scope_name,
                    expression_sql=expression_sql,
                ))
                continue
            for upstream_id in graph.upstream(node_id):
                stack.append(upstream_id)



    def _finalize_source_columns(self, scope_registry, resolver, graph: DependencyGraph, source_columns: list[str], dialect: str) -> list[str]:
        supplemented = self._supplement_union_source_columns(scope_registry, resolver, source_columns)
        supplemented = self._supplement_from_intermediate_expressions(scope_registry, resolver, graph, supplemented, dialect)
        physicalized: set[str] = set()
        for source_id in supplemented:
            physicalized.update(self._resolve_source_id_to_physical(scope_registry, resolver, source_id, set()))
        return sorted(physicalized)


    def _supplement_from_intermediate_expressions(self, scope_registry, resolver, graph: DependencyGraph, source_columns: list[str], dialect: str) -> list[str]:
        all_sources: set[str] = set(source_columns)
        for node in graph.nodes.values():
            if node.node_type != 'intermediate_feature' or not node.scope_name:
                continue

            expr = None
            alias_ref = scope_registry.find_alias(node.scope_name, node.name)
            if alias_ref is not None:
                expr = alias_ref.expression
            elif node.expression_sql:
                try:
                    expr = parse_one(node.expression_sql, read=dialect)
                except Exception:
                    expr = None

            if expr is None:
                continue

            all_sources.update(self._resolve_expression_source_ids(resolver, node.scope_name, expr))
        return sorted(all_sources)

    def _resolve_expression_source_ids(self, resolver, scope_name: str, expr) -> set[str]:
        source_ids: set[str] = set()
        for col in self.expander.collect_columns(expr):
            try:
                resolved = resolver.resolve_column(scope_name, col.copy())
            except Exception:
                continue
            for source_node in resolved.source_nodes:
                source_ids.add(source_node.node_id)
        return source_ids
    def _supplement_union_source_columns(self, scope_registry, resolver, source_columns: list[str]) -> list[str]:
        all_sources: set[str] = set(source_columns)
        for scope_record in scope_registry.iter_scopes():
            descriptor = scope_registry.get_set_operation(scope_record.scope_name)
            if descriptor is None:
                continue
            branch_specs = (
                (descriptor.left_scope_name, descriptor.left_output_expressions, descriptor.left_expression),
                (descriptor.right_scope_name, descriptor.right_output_expressions, descriptor.right_expression),
            )
            max_len = max(len(descriptor.left_output_expressions or ()), len(descriptor.right_output_expressions or ()))
            for position in range(max_len):
                branch_source_sets: list[set[str]] = []
                for branch_scope_name, branch_outputs, branch_expression in branch_specs:
                    if position >= len(branch_outputs):
                        branch_source_sets.append(set())
                        continue
                    result = resolver._resolve_branch_expression(branch_scope_name, branch_outputs[position], visited=set(), branch_expression=branch_expression, position=position)
                    branch_source_sets.append({node.node_id for node in result.source_nodes})
                if any(s & all_sources for s in branch_source_sets):
                    for s in branch_source_sets:
                        all_sources.update(s)
        return sorted(all_sources)

    def _resolve_source_id_to_physical(self, scope_registry, resolver, source_id: str, visited: set[tuple[str, str]]) -> set[str]:
        if not source_id.startswith('src:'):
            return {source_id}
        body = source_id[4:]
        if '.' not in body:
            return {source_id}
        table_name, column_name = body.rsplit('.', 1)
        key = (table_name, column_name)
        if key in visited:
            return {source_id}
        next_visited = set(visited)
        next_visited.add(key)

        source_scope_names: set[str] = set()
        for scope_record in scope_registry.iter_scopes():
            for relation in scope_registry.list_relations(scope_record.scope_name):
                if relation.relation_name == table_name or relation.alias_name == table_name:
                    if relation.source_scope_name:
                        source_scope_names.add(relation.source_scope_name)
        if not source_scope_names:
            return {source_id}

        physicalized: set[str] = set()
        for source_scope_name in source_scope_names:
            result = resolver._resolve_output_column(source_scope_name, column_name, visited=set())
            if result.source_nodes:
                for node in result.source_nodes:
                    physicalized.update(self._resolve_source_id_to_physical(scope_registry, resolver, node.node_id, next_visited))
            else:
                physicalized.add(source_id)
        return physicalized or {source_id}
