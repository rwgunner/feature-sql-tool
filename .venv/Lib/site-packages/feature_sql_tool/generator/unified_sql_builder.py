from __future__ import annotations

from feature_sql_tool.generator.cte_renderer import CteRenderer
from feature_sql_tool.generator.final_select_renderer import FinalSelectRenderer
from feature_sql_tool.models.execution_plan import ExecutionPlan
from feature_sql_tool.models.vector_build_request import VectorBuildRequest


class UnifiedSqlBuilder:
    def __init__(self) -> None:
        self.cte_renderer = CteRenderer()
        self.final_renderer = FinalSelectRenderer()

    def build(self, request: VectorBuildRequest, plan: ExecutionPlan) -> str:
        ctes: list[str] = []
        for step in plan.base_steps + plan.reusable_steps + plan.aggregate_steps:
            ctes.append(self.cte_renderer.render(step))
        for feature in request.features:
            for step in plan.feature_steps.get(feature.feature_name, []):
                ctes.append(self.cte_renderer.render(step))
        if plan.entity_step is not None:
            ctes.append(self.cte_renderer.render(plan.entity_step))
        with_clause = "WITH\n" + ",\n".join(ctes) if ctes else ""
        final_sql = self.final_renderer.render(request, plan)
        return f"{with_clause}\n{final_sql}" if with_clause else final_sql
