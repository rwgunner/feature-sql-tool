from __future__ import annotations

import json
from dataclasses import asdict

from feature_sql_tool.models.execution_plan import ExecutionPlan
from feature_sql_tool.models.reusable_subgraph import ReusableSubgraph


class OptimizationReporter:
    def to_json(self, plan: ExecutionPlan, reusable: list[ReusableSubgraph] | None = None) -> str:
        payload = {
            'plan': asdict(plan),
            'reusable_subgraphs': [asdict(item) for item in (reusable or [])],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
