from __future__ import annotations

from sqlglot import exp, parse_one

from feature_sql_tool.models.execution_plan import ExecutionPlan, ExecutionStep
from feature_sql_tool.models.vector_build_request import VectorBuildRequest
from feature_sql_tool.planner.aggregate_merger import AggregateMerger
from feature_sql_tool.planner.common_subgraph_merger import CommonSubgraphMerger
from feature_sql_tool.planner.query_graph_builder import QueryGraphBuilder
from feature_sql_tool.planner.required_columns_propagator import RequiredColumnsPropagator
from feature_sql_tool.planner.reusable_plan_validator import ReusablePlanValidator


class ReusableExecutionPlanner:
    def __init__(self) -> None:
        self.graph_builder = QueryGraphBuilder()
        self.required_columns = RequiredColumnsPropagator()
        self.base_merger = CommonSubgraphMerger()
        self.aggregate_merger = AggregateMerger()
        self.validator = ReusablePlanValidator()

    def build(self, request: VectorBuildRequest) -> ExecutionPlan:
        plans = [self.graph_builder.build(feature) for feature in request.features]
        required = self.required_columns.propagate(plans)
        base_reusable, base_mapping, _ = self.base_merger.merge_base_stages(plans, required)
        agg_reusable, agg_mapping = self.aggregate_merger.merge_aggregate_stages(plans, base_mapping)

        remapped_base_steps: list[ExecutionStep] = []
        for stage in base_reusable:
            feature_hint = stage.feature_names[0] if stage.feature_names else ''
            remapped_sql = self._remap_stage_sql(stage.raw_sql, feature_hint, base_mapping, agg_mapping)
            remapped_base_steps.append(ExecutionStep(stage.reusable_name, remapped_sql, 'reusable_base'))

        remapped_agg_steps: list[ExecutionStep] = []
        for stage in agg_reusable:
            feature_hint = stage.feature_names[0] if stage.feature_names else ''
            remapped_sql = self._remap_stage_sql(stage.raw_sql, feature_hint, base_mapping, agg_mapping)
            remapped_agg_steps.append(ExecutionStep(stage.reusable_name, remapped_sql, 'reusable_aggregate'))

        plan = ExecutionPlan()
        needed_base_names: set[str] = set()
        needed_agg_names: set[str] = set()

        for feature, feature_plan in zip(request.features, plans):
            final_stage = feature_plan.stage_by_name(feature_plan.final_stage_name)
            rewritten_sql, used_base, used_agg = self._render_feature_projection(feature, final_stage, base_mapping, agg_mapping)
            needed_base_names.update(used_base)
            needed_agg_names.update(used_agg)
            step_name = f"feature_{feature.feature_name}"
            plan.feature_steps[feature.feature_name] = [ExecutionStep(step_name, rewritten_sql, 'feature_projection')]
            plan.feature_to_step_name[feature.feature_name] = step_name
            plan.feature_to_column_name[feature.feature_name] = feature.feature_name

        for step in remapped_base_steps:
            if step.step_name in needed_base_names:
                plan.base_steps.append(step)
        for step in remapped_agg_steps:
            if step.step_name in needed_agg_names:
                plan.aggregate_steps.append(step)

        step_names = [plan.feature_to_step_name[f.feature_name] for f in request.features]
        plan.entity_step = ExecutionStep('entity_base', self._build_entity_sql(request.entity_key, step_names), 'entity')
        plan.final_step = ExecutionStep('final_select', '-- rendered by UnifiedSqlBuilder', 'final_select')
        self.validator.validate(plan)
        return plan

    def _render_feature_projection(self, feature, final_stage, base_mapping, agg_mapping):
        expr = parse_one(final_stage.raw_sql, read=feature.dialect)
        used_base: set[str] = set()
        used_agg: set[str] = set()
        for table in expr.find_all(exp.Table):
            original = table.name
            new_name = agg_mapping.get((feature.feature_name, original))
            if new_name:
                table.set('this', exp.to_identifier(new_name))
                used_agg.add(new_name)
                continue
            new_name = base_mapping.get((feature.feature_name, original))
            if new_name:
                table.set('this', exp.to_identifier(new_name))
                used_base.add(new_name)
        if expr.args.get('with') is not None:
            expr.set('with', None)
        return expr.sql(dialect=feature.dialect, pretty=False), used_base, used_agg

    def _remap_stage_sql(self, sql: str, feature_name: str, base_mapping, agg_mapping) -> str:
        try:
            expr = parse_one(sql)
        except Exception:
            return sql
        for table in expr.find_all(exp.Table):
            original = table.name
            new_name = agg_mapping.get((feature_name, original)) or base_mapping.get((feature_name, original))
            if new_name:
                table.set('this', exp.to_identifier(new_name))
        return expr.sql(pretty=False)

    def _build_entity_sql(self, entity_key: str, step_names: list[str]) -> str:
        selects = [f'SELECT DISTINCT {entity_key} FROM {step}' for step in step_names]
        return '\nUNION\n'.join(selects)
