from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DependencyNode:
    node_id: str
    node_type: str  # source_column / intermediate_feature / final_feature / relation / aggregate_feature
    name: str
    scope_name: Optional[str] = None
    source_table: Optional[str] = None
    source_column: Optional[str] = None
    expression_sql: Optional[str] = None
    grain: Optional[str] = None
    feature_name: Optional[str] = None


@dataclass(frozen=True)
class DependencyEdge:
    from_node: str
    to_node: str
    dependency_type: str  # value / filter / join / set / group / passthrough
    clause_type: str      # select / where / having / join_on / qualify / union / group_by
    scope_name: Optional[str] = None
    expression_sql: Optional[str] = None
