from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from feature_sql_tool.models.expression_ref import ExpressionRef
from feature_sql_tool.models.relation_descriptor import RelationDescriptor
from feature_sql_tool.models.set_operation_descriptor import SetOperationDescriptor


@dataclass
class ScopeRecord:
    scope_name: str
    scope_obj: Any
    expression: Any
    parent_scope_name: Optional[str] = None
    child_scope_names: list[str] = field(default_factory=list)
    relations: Dict[str, RelationDescriptor] = field(default_factory=dict)
    aliases: Dict[str, ExpressionRef] = field(default_factory=dict)
    set_operation: SetOperationDescriptor | None = None


class ScopeRegistry:
    def __init__(self) -> None:
        self._scopes: Dict[str, ScopeRecord] = {}
        self._scope_obj_ids: Dict[int, str] = {}
        self._scope_expr_ids: Dict[int, str] = {}
        self.root_scope_name: Optional[str] = None

    def register_scope(self, record: ScopeRecord) -> None:
        self._scopes[record.scope_name] = record
        if record.scope_obj is not None:
            self._scope_obj_ids[id(record.scope_obj)] = record.scope_name
        if record.expression is not None:
            self._scope_expr_ids[id(record.expression)] = record.scope_name
            if hasattr(record.expression, 'this') and record.expression.this is not None:
                self._scope_expr_ids[id(record.expression.this)] = record.scope_name
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

    def register_set_operation(self, scope_name: str, descriptor: SetOperationDescriptor) -> None:
        self._scopes[scope_name].set_operation = descriptor

    def get_set_operation(self, scope_name: str) -> SetOperationDescriptor | None:
        return self._scopes[scope_name].set_operation

    def find_alias(self, scope_name: str, alias_name: str) -> Optional[ExpressionRef]:
        scope = self._scopes[scope_name]
        return scope.aliases.get(alias_name)

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

    def find_scope_name_for_obj(self, obj: Any) -> Optional[str]:
        if obj is None:
            return None
        scope_name = self._scope_obj_ids.get(id(obj))
        if scope_name is not None:
            return scope_name
        expr = getattr(obj, 'expression', None)
        if expr is not None:
            scope_name = self._scope_expr_ids.get(id(expr))
            if scope_name is not None:
                return scope_name
        this_expr = getattr(obj, 'this', None)
        if this_expr is not None:
            scope_name = self._scope_expr_ids.get(id(this_expr))
            if scope_name is not None:
                return scope_name
        return None
