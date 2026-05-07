from __future__ import annotations

from feature_sql_tool.models.execution_plan import ExecutionPlan
from feature_sql_tool.models.vector_build_request import VectorBuildRequest


class FinalSelectRenderer:
    def render(self, request: VectorBuildRequest, plan: ExecutionPlan) -> str:
        base_name = 'entity_base' if plan.entity_step is not None else None
        if base_name is None:
            unique_steps = list(dict.fromkeys(plan.feature_to_step_name.values()))
            if not unique_steps:
                return 'SELECT 1'
            base_name = unique_steps[0]

        entity_keys = tuple(request.entity_keys or (request.entity_key,))
        select_lines = [f"base.{key}" for key in entity_keys]
        joined_steps: list[str] = []
        step_aliases: dict[str, str] = {base_name: 'base'}

        unique_steps = list(dict.fromkeys(plan.feature_to_step_name.values()))
        alias_idx = 1
        for step_name in unique_steps:
            if step_name == base_name:
                continue
            alias = f"s{alias_idx}"
            alias_idx += 1
            step_aliases[step_name] = alias
            join_condition = ' AND '.join(f"base.{key} = {alias}.{key}" for key in entity_keys)
            joined_steps.append(f"LEFT JOIN {step_name} {alias} ON {join_condition}")

        for feature in request.features:
            step_name = plan.feature_to_step_name[feature.feature_name]
            column_name = plan.feature_to_column_name[feature.feature_name]
            alias = step_aliases.get(step_name, 'base')
            select_lines.append(f"{alias}.{column_name} AS {feature.feature_name}")

        lines = ["SELECT", "    " + ",\n    ".join(select_lines), f"FROM {base_name} base"]
        if joined_steps:
            lines.extend(joined_steps)
        return "\n".join(lines)
