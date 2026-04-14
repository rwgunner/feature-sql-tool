from __future__ import annotations

from typing import Optional

from sqlglot import exp

from feature_sql_tool.graph.classifier import GraphClassifier
from feature_sql_tool.graph.dependency_graph import DependencyGraph
from feature_sql_tool.lineage.column_resolver import ColumnResolver
from feature_sql_tool.lineage.expression_dependencies import ExpressionDependencyExtractor
from feature_sql_tool.lineage.filter_collector import FilterDependencyCollector
from feature_sql_tool.models.feature_spec import FeatureSpec
from feature_sql_tool.models.graph import DependencyEdge, DependencyNode
from feature_sql_tool.models.lineage_result import FeatureLineageResult
from feature_sql_tool.parser.ast_normalizer import AstNormalizer
from feature_sql_tool.parser.sql_parser import SqlParser


class FeatureLineageExtractor:
    def __init__(self) -> None:
        self.sql_parser = SqlParser()
        self.column_resolver = ColumnResolver()
        self.expr_deps = ExpressionDependencyExtractor()
        self.filter_collector = FilterDependencyCollector()
        self.classifier = GraphClassifier()
        self.normalizer = AstNormalizer()

    def extract(self, feature_spec: FeatureSpec) -> FeatureLineageResult:
        parse_result = self.sql_parser.parse_feature(feature_spec)
        graph = DependencyGraph()

        final_node_id = f"fin:{feature_spec.feature_name}"
        final_node = DependencyNode(
            node_id=final_node_id,
            node_type="final_feature",
            name=feature_spec.final_alias,
            feature_name=feature_spec.feature_name,
        )
        graph.add_node(final_node)

        final_select_expression = self._find_final_select_expression(
            parse_result.expression,
            feature_spec.final_alias,
        )

        if final_select_expression is not None:
            final_expr_sql = self.normalizer.normalize_expression_sql(
                final_select_expression, feature_spec.dialect
            )
            intermediate_node_id = f"int:{feature_spec.feature_name}:{feature_spec.final_alias}"

            graph.add_node(
                DependencyNode(
                    node_id=intermediate_node_id,
                    node_type="intermediate_feature",
                    name=feature_spec.final_alias,
                    scope_name="root",
                    expression_sql=final_expr_sql,
                    feature_name=feature_spec.feature_name,
                )
            )
            graph.add_edge(
                DependencyEdge(
                    from_node=intermediate_node_id,
                    to_node=final_node_id,
                    dependency_type="value",
                    clause_type="select",
                    scope_name="root",
                    expression_sql=final_expr_sql,
                )
            )

            for column in self.expr_deps.extract_columns(final_select_expression):
                resolved = self.column_resolver.resolve_column(column)
                source_node_id = f"src:{resolved['table_name']}.{resolved['column_name']}"

                graph.add_node(
                    DependencyNode(
                        node_id=source_node_id,
                        node_type="source_column",
                        name=f"{resolved['table_name']}.{resolved['column_name']}",
                        source_table=resolved["table_name"],
                        source_column=resolved["column_name"],
                        feature_name=feature_spec.feature_name,
                    )
                )
                graph.add_edge(
                    DependencyEdge(
                        from_node=source_node_id,
                        to_node=intermediate_node_id,
                        dependency_type="value",
                        clause_type="select",
                        scope_name="root",
                        expression_sql=str(column),
                    )
                )

        filters = self.filter_collector.collect(parse_result.expression)
        for clause_type, columns in filters.items():
            for column in columns:
                resolved = self.column_resolver.resolve_column(column)
                source_node_id = f"src:{resolved['table_name']}.{resolved['column_name']}"

                graph.add_node(
                    DependencyNode(
                        node_id=source_node_id,
                        node_type="source_column",
                        name=f"{resolved['table_name']}.{resolved['column_name']}",
                        source_table=resolved["table_name"],
                        source_column=resolved["column_name"],
                        feature_name=feature_spec.feature_name,
                    )
                )
                graph.add_edge(
                    DependencyEdge(
                        from_node=source_node_id,
                        to_node=final_node_id,
                        dependency_type="filter" if clause_type != "join_on" else "join",
                        clause_type=clause_type,
                        scope_name="root",
                        expression_sql=str(column),
                    )
                )

        return FeatureLineageResult(
            feature_spec=feature_spec,
            nodes=graph.nodes,
            edges=graph.edges,
            source_columns=self.classifier.classify_source_columns(graph),
            filter_only_intermediate_features=self.classifier.classify_filter_only_intermediate_features(graph),
            intermediate_features=self.classifier.classify_intermediate_features(graph),
        )

    def _find_final_select_expression(self, root_expression, final_alias: str) -> Optional[object]:
        """Find the expression for the select item with alias == final_alias."""
        select_expressions = getattr(root_expression, "expressions", []) or []
        for expression in select_expressions:
            alias = expression.alias_or_name
            if alias == final_alias:
                return expression.this if isinstance(expression, exp.Alias) else expression
        return None
