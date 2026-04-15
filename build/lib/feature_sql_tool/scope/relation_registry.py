from __future__ import annotations

from feature_sql_tool.models.relation_descriptor import RelationDescriptor
from feature_sql_tool.scope.scope_registry import ScopeRegistry


class RelationRegistry:
    def __init__(self, scope_registry: ScopeRegistry) -> None:
        self.scope_registry = scope_registry

    def register_relation(self, scope_name: str, relation: RelationDescriptor) -> None:
        self.scope_registry.register_relation(scope_name, relation)

    def get_relation(self, scope_name: str, relation_name: str) -> RelationDescriptor | None:
        return self.scope_registry.find_relation(scope_name, relation_name)
