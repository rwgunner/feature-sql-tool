from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from feature_sql_tool.models.feature_spec import FeatureSpec
from feature_sql_tool.models.graph import DependencyEdge, DependencyNode


@dataclass
class FeatureLineageResult:
    feature_spec: FeatureSpec
    nodes: Dict[str, DependencyNode] = field(default_factory=dict)
    edges: List[DependencyEdge] = field(default_factory=list)
    source_columns: List[str] = field(default_factory=list)
    filter_only_intermediate_features: List[str] = field(default_factory=list)
    intermediate_features: List[str] = field(default_factory=list)
