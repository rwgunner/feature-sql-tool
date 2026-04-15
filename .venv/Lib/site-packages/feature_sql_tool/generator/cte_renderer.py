from __future__ import annotations

from feature_sql_tool.models.execution_plan import ExecutionStep


class CteRenderer:
    def render(self, step: ExecutionStep) -> str:
        return f"{step.step_name} AS (\n{step.sql}\n)"
