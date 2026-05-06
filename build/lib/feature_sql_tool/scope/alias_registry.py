from __future__ import annotations

from feature_sql_tool.models.expression_ref import ExpressionRef
from feature_sql_tool.scope.scope_registry import ScopeRegistry


class AliasRegistry:
    def __init__(self, scope_registry: ScopeRegistry) -> None:
        self.scope_registry = scope_registry

    def register_alias(self, scope_name: str, expression_ref: ExpressionRef) -> None:
        self.scope_registry.register_alias(scope_name, expression_ref)

    def find_alias(self, scope_name: str, alias_name: str) -> ExpressionRef | None:
        return self.scope_registry.find_alias(scope_name, alias_name)
