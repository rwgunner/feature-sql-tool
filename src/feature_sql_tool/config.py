from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSqlToolConfig:
    default_dialect: str = "spark"
    include_case_filter_dependencies: bool = True
    include_group_by_dependencies: bool = True
    unify_identical_ctes: bool = True
    allow_partial_subgraph_merge: bool = False
