from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ResolvedColumn:
    scope_name: str
    source_kind: str  # physical_table / cte / subquery / alias / unresolved
    table_name: Optional[str]
    column_name: str
    relation_name: Optional[str]
    upstream_alias_name: Optional[str] = None
