from __future__ import annotations

from feature_sql_tool.models.execution_plan import ExecutionStep
from feature_sql_tool.models.reusable_subgraph import ReusableSubgraph


class AggregateStepBuilder:
    def build(self, subgraph: ReusableSubgraph) -> ExecutionStep:
        sql = f"-- reusable aggregate: {subgraph.signature}\nSELECT 1 AS placeholder"
        return ExecutionStep(step_name=subgraph.subgraph_id, sql=sql, step_type='reusable_aggregate')
