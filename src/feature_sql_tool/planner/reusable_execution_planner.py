from __future__ import annotations

from sqlglot import exp, parse_one

from feature_sql_tool.models.execution_plan import ExecutionPlan, ExecutionStep
from feature_sql_tool.models.feature_spec import FeatureSpec
from feature_sql_tool.models.query_plan import FeatureQueryPlan
from feature_sql_tool.models.vector_build_request import VectorBuildRequest
from feature_sql_tool.planner.aggregate_merger import AggregateMerger
from feature_sql_tool.planner.common_subgraph_merger import CommonSubgraphMerger
from feature_sql_tool.planner.query_graph_builder import QueryGraphBuilder
from feature_sql_tool.planner.required_columns_propagator import RequiredColumnsPropagator


class ReusableExecutionPlanner:
    def __init__(self) -> None:
        self.graph_builder = QueryGraphBuilder()
        self.required_columns = RequiredColumnsPropagator()
        self.base_merger = CommonSubgraphMerger()
        self.aggregate_merger = AggregateMerger()

    def build(self, request: VectorBuildRequest) -> ExecutionPlan:
        plans = [self.graph_builder.build(feature) for feature in request.features]
        required = self.required_columns.propagate(plans)
        base_reusable, base_mapping, _ = self.base_merger.merge_base_stages(plans, required)
        agg_reusable, agg_mapping = self.aggregate_merger.merge_aggregate_stages(plans, base_mapping)

        plan = ExecutionPlan()
        for stage in base_reusable:
            plan.base_steps.append(ExecutionStep(stage.reusable_name, stage.raw_sql, 'reusable_base'))
        for stage in agg_reusable:
            plan.aggregate_steps.append(ExecutionStep(stage.reusable_name, stage.raw_sql, 'reusable_aggregate'))

        for feature, feature_plan in zip(request.features, plans):
            final_stage = feature_plan.stage_by_name(feature_plan.final_stage_name)
            feature_sql = self._render_feature_projection(feature, final_stage, base_mapping, agg_mapping)
            step_name = f"feature_{feature.feature_name}"
            plan.feature_steps[feature.feature_name] = [ExecutionStep(step_name, feature_sql, 'feature_projection')]
            plan.feature_to_step_name[feature.feature_name] = step_name
            plan.feature_to_column_name[feature.feature_name] = feature.feature_name

        step_names = [plan.feature_to_step_name[f.feature_name] for f in request.features]
        plan.entity_step = ExecutionStep('entity_base', self._build_entity_sql(request.entity_key, step_names), 'entity')
        plan.final_step = ExecutionStep('final_select', '-- rendered by UnifiedSqlBuilder', 'final_select')
        return plan

    def _render_feature_projection(self, feature: FeatureSpec, final_stage, base_mapping, agg_mapping) -> str:
        expr = parse_one(final_stage.raw_sql, read=feature.dialect)
        self._rewrite_tables(expr, base_mapping, agg_mapping, feature.feature_name)
        if expr.args.get('with') is not None:
            expr.set('with', None)
        return expr.sql(dialect=feature.dialect, pretty=False)

    def _rewrite_tables(self, expr, base_mapping, agg_mapping, feature_name: str) -> None:
        for table in expr.find_all(exp.Table):
            original = table.name
            new_name = agg_mapping.get((feature_name, original)) or base_mapping.get((feature_name, original))
            if new_name:
                table.set('this', exp.to_identifier(new_name))

    def _build_entity_sql(self, entity_key: str, step_names: list[str]) -> str:
        selects = [f'SELECT DISTINCT {entity_key} FROM {step}' for step in step_names]
        return '\nUNION\n'.join(selects)
