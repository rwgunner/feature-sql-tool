from __future__ import annotations

import json
from dataclasses import asdict

from feature_sql_tool.models.execution_plan import ExecutionPlan


class PlanReporter:
    def to_json(self, plan: ExecutionPlan) -> str:
        return json.dumps(asdict(plan), ensure_ascii=False, indent=2, default=str)
