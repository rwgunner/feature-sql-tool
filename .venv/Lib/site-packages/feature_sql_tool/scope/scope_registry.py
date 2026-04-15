from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from feature_sql_tool.models.expression_ref import ExpressionRef
from feature_sql_tool.models.relation_descriptor import RelationDescriptor


@dataclass
class ScopeRecord:
    scope_name: str
    scope_obj: Any
    expression: Any
    parent_scope_name: Optional[str] = None
    child_scope_names: list[str] = field(default_factory=list)
    relations: Dict[str, RelationDescriptor] = field(default_factory=dict)
    aliases: Dict[str, ExpressionRef] = field(default_factory=dict)


class ScopeRegistry:
    def __init__(self) -> None:
        self._scopes: Dict[str, ScopeRecord] = {}
        self.root_scope_name: Optional[str] = None

    def register_scope(self, record: ScopeRecord) -> None:
        self._scopes[record.scope_name] = record
        if record.parent_scope_name and record.parent_scope_name in self._scopes:
            parent = self._scopes[record.parent_scope_name]
            if record.scope_name not in parent.child_scope_names:
                parent.child_scope_names.append(record.scope_name)

    def set_root_scope(self, scope_name: str | None) -> None:
        self.root_scope_name = scope_name

    def get_scope(self, scope_name: str) -> ScopeRecord:
        return self._scopes[scope_name]

    def iter_scopes(self) -> Iterator[ScopeRecord]:
        return iter(self._scopes.values())

    def register_relation(self, scope_name: str, relation: RelationDescriptor) -> None:
        self._scopes[scope_name].relations[relation.relation_name] = relation
        if relation.source_scope_name and relation.source_scope_name in self._scopes:
            parent = self._scopes[relation.source_scope_name]
            if scope_name not in parent.child_scope_names:
                parent.child_scope_names.append(scope_name)

    def register_alias(self, scope_name: str, expression_ref: ExpressionRef) -> None:
        self._scopes[scope_name].aliases[expression_ref.alias_name] = expression_ref

    def find_alias(self, scope_name: str, alias_name: str) -> Optional[ExpressionRef]:
        scope = self._scopes[scope_name]
        if alias_name in scope.aliases:
            return scope.aliases[alias_name]
        return None

    def find_relation(self, scope_name: str, relation_name: str) -> Optional[RelationDescriptor]:
        scope = self._scopes[scope_name]
        if relation_name in scope.relations:
            return scope.relations[relation_name]
        for relation in scope.relations.values():
            if relation.alias_name == relation_name or relation.physical_table_name == relation_name:
                return relation
        return None

    def list_relations(self, scope_name: str) -> list[RelationDescriptor]:
        return list(self._scopes[scope_name].relations.values())
