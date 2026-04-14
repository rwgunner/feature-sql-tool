from __future__ import annotations

from typing import Iterable

from feature_sql_tool.models.execution_plan import ExecutionPlan
from feature_sql_tool.models.feature_spec import FeatureSpec


class UnifiedSqlBuilder:
    """
    Simplest version:
    - each feature becomes a CTE
    - final SELECT is assembled with LEFT JOINs on entity_key
    """

    def build(self, feature_specs: Iterable[FeatureSpec], plan: ExecutionPlan) -> str:
        specs = list(feature_specs)
        if not specs:
            raise ValueError("No feature specs provided.")

        entity_key = specs[0].entity_key

        cte_blocks = []
        for spec in specs:
            feature_steps = plan.feature_steps.get(spec.feature_name, [])
            if not feature_steps:
                continue
            step = feature_steps[0]
            cte_blocks.append(f"{spec.feature_name}__cte AS (\n{step.sql}\n)")

        with_clause = "WITH\n" + ",\n".join(cte_blocks)

        base_feature = specs[0]
        select_parts = [f"base.{entity_key}"]
        from_clause = f"FROM {base_feature.feature_name}__cte base"

        join_parts = []
        for spec in specs:
            alias = spec.feature_name
            if spec.feature_name == base_feature.feature_name:
                select_parts.append(f"base.{spec.final_alias} AS {spec.feature_name}")
                continue

            join_parts.append(
                f"LEFT JOIN {alias}__cte {alias} ON base.{entity_key} = {alias}.{entity_key}"
            )
            select_parts.append(f"{alias}.{spec.final_alias} AS {spec.feature_name}")

        final_sql = (
            f"{with_clause}\n"
            f"SELECT\n    " + ",\n    ".join(select_parts) + "\n"
            f"{from_clause}\n"
            + ("\n".join(join_parts) if join_parts else "")
        )
        return final_sql
