from __future__ import annotations

from sqlglot import parse_one
from sqlglot.optimizer.scope import build_scope, traverse_scope

from feature_sql_tool.exceptions import SqlParseError
from feature_sql_tool.models.feature_spec import FeatureSpec
from feature_sql_tool.models.parse_result import ParseResult
from feature_sql_tool.parser.scope_registry import ScopeInfo, ScopeRegistry
from feature_sql_tool.parser.sql_loader import SqlFileLoader


class SqlParser:
    def __init__(self, loader: SqlFileLoader | None = None) -> None:
        self.loader = loader or SqlFileLoader()

    def parse_feature(self, feature_spec: FeatureSpec) -> ParseResult:
        feature_spec.validate()
        raw_sql = self.loader.load(feature_spec.sql_file_path)

        try:
            expression = parse_one(raw_sql, read=feature_spec.dialect)
        except Exception as exc:
            raise SqlParseError(
                f"Failed to parse SQL for feature '{feature_spec.feature_name}': {exc}"
            ) from exc

        try:
            build_scope(expression)
            traversed_scopes = traverse_scope(expression)
        except Exception as exc:
            raise SqlParseError(
                f"Failed to build scopes for feature '{feature_spec.feature_name}': {exc}"
            ) from exc

        registry = ScopeRegistry()
        for i, scope in enumerate(traversed_scopes):
            scope_name = f"{feature_spec.feature_name}__scope_{i}"
            source_names = list(getattr(scope, "sources", {}).keys())
            registry.add_scope(
                ScopeInfo(
                    scope_name=scope_name,
                    scope_obj=scope,
                    expression=getattr(scope, "expression", None),
                    parent_scope_name=None,
                    source_names=source_names,
                )
            )

        if registry.root_scope_name is None and traversed_scopes:
            registry.root_scope_name = f"{feature_spec.feature_name}__scope_0"

        return ParseResult(
            feature_spec=feature_spec,
            raw_sql=raw_sql,
            expression=expression,
            scope_registry=registry,
        )
