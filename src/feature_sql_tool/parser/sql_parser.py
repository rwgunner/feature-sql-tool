from __future__ import annotations

from typing import Any

from sqlglot import exp, parse_one
from sqlglot.optimizer.scope import build_scope, traverse_scope

from feature_sql_tool.models.expression_ref import ExpressionRef
from feature_sql_tool.models.parse_result import ParseResult
from feature_sql_tool.models.relation_descriptor import RelationDescriptor
from feature_sql_tool.parser.ast_normalizer import AstNormalizer
from feature_sql_tool.parser.sql_loader import SqlFileLoader
from feature_sql_tool.scope.passthrough_detector import PassthroughDetector
from feature_sql_tool.scope.scope_registry import ScopeRecord, ScopeRegistry


class SqlParser:
    def __init__(self, loader: SqlFileLoader | None = None) -> None:
        self.loader = loader or SqlFileLoader()
        self.normalizer = AstNormalizer()
        self.passthrough_detector = PassthroughDetector()

    def parse_feature(self, feature_spec) -> ParseResult:
        feature_spec.validate()
        raw_sql = self.loader.load(feature_spec.sql_file_path)
        expression = parse_one(raw_sql, read=feature_spec.dialect)

        build_scope(expression)
        scopes = list(traverse_scope(expression))
        registry = ScopeRegistry()
        scope_id_to_name: dict[int, str] = {}

        for i, scope in enumerate(scopes):
            scope_name = f"{feature_spec.feature_name}__scope_{i}"
            scope_id_to_name[id(scope)] = scope_name
            parent_scope_name = scope_id_to_name.get(id(getattr(scope, 'parent', None)))
            registry.register_scope(
                ScopeRecord(
                    scope_name=scope_name,
                    scope_obj=scope,
                    expression=getattr(scope, 'expression', None),
                    parent_scope_name=parent_scope_name,
                )
            )

        for scope in scopes:
            scope_name = scope_id_to_name[id(scope)]
            self._register_relations(feature_spec.dialect, registry, scope_name, scope, scope_id_to_name)
            self._register_aliases(feature_spec.dialect, registry, scope_name, scope)

        return ParseResult(feature_spec=feature_spec, raw_sql=raw_sql, expression=expression, scope_registry=registry)

    def _register_relations(self, dialect: str, registry: ScopeRegistry, scope_name: str, scope: Any, scope_id_to_name: dict[int, str]) -> None:
        sources = getattr(scope, 'sources', {}) or {}
        for relation_name, source_obj in sources.items():
            relation_type = 'unknown'
            physical_table_name = None
            source_scope_name = None
            alias_name = relation_name

            if isinstance(source_obj, exp.Table):
                relation_type = 'physical_table'
                physical_table_name = source_obj.name
                alias_name = source_obj.alias_or_name or relation_name
            elif id(source_obj) in scope_id_to_name:
                relation_type = 'scope_source'
                source_scope_name = scope_id_to_name[id(source_obj)]
            elif getattr(source_obj, 'expression', None) is not None and id(source_obj) in scope_id_to_name:
                relation_type = 'scope_source'
                source_scope_name = scope_id_to_name[id(source_obj)]
            elif isinstance(source_obj, exp.Subquery):
                relation_type = 'subquery'
            elif relation_name:
                # most CTE references appear here as Scope objects; keep a permissive fallback
                relation_type = 'cte'

            registry.register_relation(
                scope_name,
                RelationDescriptor(
                    relation_name=relation_name,
                    relation_type=relation_type,
                    scope_name=scope_name,
                    source_scope_name=source_scope_name,
                    physical_table_name=physical_table_name,
                    alias_name=alias_name,
                ),
            )

    def _register_aliases(self, dialect: str, registry: ScopeRegistry, scope_name: str, scope: Any) -> None:
        select_items = getattr(getattr(scope, 'expression', None), 'expressions', []) or []
        for item in select_items:
            alias_name = getattr(item, 'alias_or_name', None)
            if not alias_name:
                continue
            expression = item.this if isinstance(item, exp.Alias) else item
            passthrough_column = self.passthrough_detector.extract_passthrough_column(expression)
            is_passthrough = passthrough_column is not None
            registry.register_alias(
                scope_name,
                ExpressionRef(
                    scope_name=scope_name,
                    alias_name=alias_name,
                    expression=expression,
                    expression_sql=self.normalizer.normalize_expression_sql(expression, dialect),
                    is_computed=not is_passthrough,
                    is_passthrough=is_passthrough,
                    passthrough_column=passthrough_column,
                ),
            )
