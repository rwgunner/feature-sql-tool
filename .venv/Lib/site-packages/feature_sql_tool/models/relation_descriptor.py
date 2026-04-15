from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RelationDescriptor:
    relation_name: str
    relation_type: str  # physical_table / cte / subquery / union_branch / scope_source / unknown
    scope_name: str
    source_scope_name: Optional[str] = None
    physical_table_name: Optional[str] = None
    alias_name: Optional[str] = None
