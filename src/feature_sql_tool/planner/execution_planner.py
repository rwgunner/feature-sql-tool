from __future__ import annotations

from typing import Iterable

from feature_sql_tool.models.execution_plan import ExecutionPlan, ExecutionStep
from feature_sql_tool.models.lineage_result import FeatureLineageResult


class ExecutionPlanner:
    """
    First version: one feature-specific CTE step per feature.
    Reusable and base steps can be added later.
    """

    def build_plan(self, results: Iterable[FeatureLineageResult]) -> ExecutionPlan:
        plan = ExecutionPlan()

        for result in results:
            feature_name = result.feature_spec.feature_name
            sql = result.feature_spec.sql_file_path.read_text(encoding="utf-8")

            plan.feature_steps[feature_name] = [
                ExecutionStep(
                    step_name=f"{feature_name}_cte",
                    sql=sql,
                    step_type="feature_cte",
                )
            ]

        return plan
