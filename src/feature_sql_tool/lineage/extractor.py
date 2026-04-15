from __future__ import annotations

from sqlglot import exp

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


class FeatureLineageExtractorV2:
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

        final_expr_ref = scope_registry.find_alias(root_scope_name, feature_spec.final_alias)
        if final_expr_ref is None:
            final_expr = self._find_final_expression(root_record.expression, feature_spec.final_alias)
            if final_expr is None:
                raise ValueError(
                    f"Final alias '{feature_spec.final_alias}' was not found in root scope for feature '{feature_spec.feature_name}'"
                )
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
                grain=feature_spec.grain,
                feature_name=feature_spec.feature_name,
            )
        )

        # Value lineage for the final feature.
        for col in self.expander.collect_columns(final_expr):
            resolved = resolver.resolve_column(root_scope_name, col.copy())
            self._merge_resolution(graph, resolved)
            for terminal_id in resolved.terminal_node_ids:
                graph.add_edge(
                    DependencyEdge(
                        from_node=terminal_id,
                        to_node=final_node_id,
                        dependency_type='value',
                        clause_type='select',
                        scope_name=root_scope_name,
                        expression_sql=str(col),
                    )
                )

        # Filter lineage from all relevant scopes.
        for scope_record in scope_registry.iter_scopes():
            filters = filter_collector.collect(scope_record.expression)
            for clause_type, columns in filters.items():
                dependency_type = 'join' if clause_type == 'join_on' else 'filter'
                for col in columns:
                    resolved = resolver.resolve_column(scope_record.scope_name, col.copy())
                    self._merge_resolution(graph, resolved)
                    for terminal_id in resolved.terminal_node_ids:
                        graph.add_edge(
                            DependencyEdge(
                                from_node=terminal_id,
                                to_node=final_node_id,
                                dependency_type=dependency_type,
                                clause_type=clause_type,
                                scope_name=scope_record.scope_name,
                                expression_sql=str(col),
                            )
                        )

        return FeatureLineageResult(
            feature_spec=feature_spec,
            nodes=graph.nodes,
            edges=graph.edges,
            source_columns=self.classifier.classify_source_columns(graph),
            intermediate_features=self.classifier.classify_intermediate_features(graph),
            filter_only_intermediate_features=self.filter_only.classify(graph, final_node_id),
        )

    def _merge_resolution(self, graph: DependencyGraph, resolved) -> None:
        for node in resolved.source_nodes + resolved.intermediate_nodes:
            graph.add_node(node)
        for edge in resolved.edges:
            graph.add_edge(edge)

    def _find_final_expression(self, expression, final_alias: str):
        select_items = getattr(expression, 'expressions', []) or []
        for item in select_items:
            if getattr(item, 'alias_or_name', None) == final_alias:
                return item.this if isinstance(item, exp.Alias) else item
        return None
