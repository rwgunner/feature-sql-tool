from __future__ import annotations

from collections import defaultdict

from feature_sql_tool.models.query_plan import FeatureQueryPlan
from feature_sql_tool.planner.node_canonicalizer import NodeCanonicalizer


class RequiredColumnsPropagator:
    def __init__(self) -> None:
        self.canonicalizer = NodeCanonicalizer()

    def propagate(self, plans: list[FeatureQueryPlan]) -> dict[tuple, set[tuple[str, str]]]:
        required: dict[tuple, set[tuple[str, str]]] = defaultdict(set)
        for plan in plans:
            for stage in plan.stages:
                if stage.stage_type != 'source_projection':
                    continue
                sig = self.canonicalizer.base_signature(stage)
                required[sig].update(stage.select_items)
        return required
