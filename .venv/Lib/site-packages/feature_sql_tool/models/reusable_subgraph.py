from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReusableSubgraph:
    subgraph_id: str
    subgraph_type: str  # base_relation / filtered_relation / aggregate_relation / computed_relation
    node_ids: list[str]
    signature: str
    grain: Optional[str] = None
