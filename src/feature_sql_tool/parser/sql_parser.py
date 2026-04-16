from __future__ import annotations

from typing import Any

from sqlglot import exp, parse_one
from sqlglot.optimizer.scope import build_scope, traverse_scope

from feature_sql_tool.models.expression_ref import ExpressionRef
from feature_sql_tool.models.parse_result import ParseResult
from feature_sql_tool.models.relation_descriptor import RelationDescriptor
from feature_sql_tool.models.set_operation_descriptor import SetOperationDescriptor
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

        root_scope = build_scope(expression)
        traversed_scopes = list(traverse_scope(expression))

        scopes: list[Any] = []
        if root_scope is not None:
            scopes.append(root_scope)
        seen_scope_ids = {id(root_scope)} if root_scope is not None else set()
        for scope in traversed_scopes:
            if id(scope) not in seen_scope_ids:
                scopes.append(scope)
                seen_scope_ids.add(id(scope))

        registry = ScopeRegistry()
        scope_id_to_name: dict[int, str] = {}

        for i, scope in enumerate(scopes):
            scope_name = f"{feature_spec.feature_name}__scope_{i}"
            scope_id_to_name[id(scope)] = scope_name

        for scope in scopes:
            scope_name = scope_id_to_name[id(scope)]
            parent_scope = getattr(scope, "parent", None)
            parent_scope_name = scope_id_to_name.get(id(parent_scope)) if parent_scope is not None else None
            registry.register_scope(
                ScopeRecord(
                    scope_name=scope_name,
                    scope_obj=scope,
                    expression=getattr(scope, "expression", None),
                    parent_scope_name=parent_scope_name,
                )
            )

        for scope in scopes:
            scope_name = scope_id_to_name[id(scope)]
            self._register_relations(feature_spec.dialect, registry, scope_name, scope)
            self._register_aliases(feature_spec.dialect, registry, scope_name, scope)
            self._register_set_operation(registry, scope_name, scope)

        registry.set_root_scope(registry.find_scope_name_for_obj(root_scope) if root_scope is not None else None)

        return ParseResult(
            feature_spec=feature_spec,
            raw_sql=raw_sql,
            expression=expression,
            scope_registry=registry,
        )

    def _register_relations(self, dialect: str, registry: ScopeRegistry, scope_name: str, scope: Any) -> None:
        selected_sources = getattr(scope, 'selected_sources', None)
        if selected_sources:
            for relation_name, (_node, source_obj) in selected_sources.items():
                registry.register_relation(scope_name, self._build_relation_descriptor(registry, scope_name, relation_name, source_obj))
            return

        sources = getattr(scope, 'sources', {}) or {}
        for relation_name, source_obj in sources.items():
            registry.register_relation(scope_name, self._build_relation_descriptor(registry, scope_name, relation_name, source_obj))

    def _build_relation_descriptor(self, registry: ScopeRegistry, scope_name: str, relation_name: str, source_obj: Any) -> RelationDescriptor:
        relation_type = 'unknown'
        physical_table_name = None
        source_scope_name = None
        alias_name = relation_name

        if isinstance(source_obj, exp.Table):
            relation_type = 'physical_table'
            physical_table_name = source_obj.name
            alias_name = source_obj.alias_or_name or relation_name
        else:
            source_scope_name = registry.find_scope_name_for_obj(source_obj)
            if source_scope_name:
                expression = registry.get_scope(source_scope_name).expression
                if isinstance(expression, exp.SetOperation):
                    relation_type = 'set_operation'
                elif getattr(source_obj, 'is_cte', False):
                    relation_type = 'cte'
                elif getattr(source_obj, 'is_subquery', False) or isinstance(source_obj, exp.Subquery):
                    relation_type = 'subquery'
                elif getattr(source_obj, 'is_derived_table', False):
                    relation_type = 'derived_table'
                else:
                    relation_type = 'scope_source'
            elif isinstance(source_obj, exp.Subquery):
                relation_type = 'subquery'
            elif relation_name:
                relation_type = 'cte'

        return RelationDescriptor(
            relation_name=relation_name,
            relation_type=relation_type,
            scope_name=scope_name,
            source_scope_name=source_scope_name,
            physical_table_name=physical_table_name,
            alias_name=alias_name,
        )

    def _register_aliases(self, dialect: str, registry: ScopeRegistry, scope_name: str, scope: Any) -> None:
        expression = getattr(scope, 'expression', None)
        select_items = getattr(expression, 'expressions', []) or []
        for item in select_items:
            alias_name = getattr(item, 'alias_or_name', None)
            if not alias_name:
                continue
            expression_item = item.this if isinstance(item, exp.Alias) else item
            passthrough_column = self.passthrough_detector.extract_passthrough_column(expression_item)
            is_passthrough = passthrough_column is not None
            registry.register_alias(
                scope_name,
                ExpressionRef(
                    scope_name=scope_name,
                    alias_name=alias_name,
                    expression=expression_item,
                    expression_sql=self.normalizer.normalize_expression_sql(expression_item, dialect),
                    is_computed=not is_passthrough,
                    is_passthrough=is_passthrough,
                    passthrough_column=passthrough_column,
                ),
            )

    def _register_set_operation(self, registry: ScopeRegistry, scope_name: str, scope: Any) -> None:
        expression = getattr(scope, 'expression', None)
        if not isinstance(expression, exp.SetOperation):
            return

        left_expr = getattr(expression, 'left', None)
        right_expr = getattr(expression, 'right', None)
        left_scope_name = registry.find_scope_name_for_obj(left_expr)
        right_scope_name = registry.find_scope_name_for_obj(right_expr)
        output_columns = tuple(self._extract_output_columns(expression))
        registry.register_set_operation(
            scope_name,
            SetOperationDescriptor(
                scope_name=scope_name,
                operation_type=expression.key.lower(),
                left_scope_name=left_scope_name,
                right_scope_name=right_scope_name,
                output_columns=output_columns,
            ),
        )

    def _extract_output_columns(self, expression: Any) -> list[str]:
        if isinstance(expression, exp.SetOperation):
            return self._extract_output_columns(getattr(expression, 'left', None))
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
