from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RelationDescriptor:
    relation_name: str
    relation_type: str  # physical_table / cte / subquery / union_branch / set_operation / scope_source / unknown
    scope_name: str
    source_scope_name: str | None = None
    physical_table_name: str | None = None
    alias_name: str | None = None
