from __future__ import annotations

from feature_sql_tool.scope.scope_registry import ScopeRegistry


class AliasResolver:
    def __init__(self, scope_registry: ScopeRegistry) -> None:
        self.scope_registry = scope_registry

    def resolve_alias(self, scope_name: str, alias_name: str):
        return self.scope_registry.find_alias(scope_name, alias_name)
