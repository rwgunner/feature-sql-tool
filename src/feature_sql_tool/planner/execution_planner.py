from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
from typing import Iterable

from sqlglot import exp

from feature_sql_tool.models.execution_plan import ExecutionPlan, ExecutionStep
from feature_sql_tool.models.lineage_result import FeatureLineageResult
from feature_sql_tool.models.vector_build_request import VectorBuildRequest
from feature_sql_tool.parser.ast_normalizer import AstNormalizer
from feature_sql_tool.parser.sql_parser import SqlParser


@dataclass(frozen=True)
class QueryShape:
    feature_name: str
    entity_key: str
    entity_expr_sql: str
    final_alias: str
    final_expr_sql: str
    with_sql: str
    from_sql: str
    joins_sql: tuple[str, ...]
    where_sql: str
    group_sql: str
    having_sql: str
    qualify_sql: str

    @property
    def base_signature(self) -> tuple:
        return (self.with_sql, self.from_sql, self.joins_sql, self.where_sql)

    @property
    def aggregate_signature(self) -> tuple:
        return (
            self.with_sql,
            self.from_sql,
            self.joins_sql,
            self.where_sql,
            self.group_sql,
            self.having_sql,
            self.qualify_sql,
            self.entity_expr_sql,
        )


class ExecutionPlannerV2:
    def __init__(self) -> None:
        self.sql_parser = SqlParser()
        self.normalizer = AstNormalizer()

    def build_plan(self, lineage_results: Iterable[FeatureLineageResult], request: VectorBuildRequest) -> ExecutionPlan:
        results = list(lineage_results)
        plan = ExecutionPlan()
        shapes = [self._shape_from_result(result) for result in results]

        aggregate_groups: dict[tuple, list[QueryShape]] = {}
        for shape in shapes:
            aggregate_groups.setdefault(shape.aggregate_signature, []).append(shape)

        for idx, (signature, group_shapes) in enumerate(aggregate_groups.items(), start=1):
            step_name = self._step_name('agg', signature, idx)
            step_sql = self._build_group_cte_sql(group_shapes)
            step_type = 'reusable_aggregate' if len(group_shapes) > 1 else 'feature'
            step = ExecutionStep(step_name=step_name, sql=step_sql, step_type=step_type)
            if len(group_shapes) > 1:
                plan.aggregate_steps.append(step)
            else:
                feature_name = group_shapes[0].feature_name
                plan.feature_steps.setdefault(feature_name, []).append(step)
            for shape in group_shapes:
                plan.feature_to_step_name[shape.feature_name] = step_name
                plan.feature_to_column_name[shape.feature_name] = shape.final_alias

        if request.entity_sql_file_path is not None:
            entity_sql = request.entity_sql_file_path.read_text(encoding='utf-8')
            plan.entity_step = ExecutionStep(step_name='entity_base', sql=entity_sql, step_type='entity')
        elif plan.feature_to_step_name:
            entity_sql = self._build_entity_sql(request.entity_key, list(dict.fromkeys(plan.feature_to_step_name.values())))
            plan.entity_step = ExecutionStep(step_name='entity_base', sql=entity_sql, step_type='entity')

        plan.final_step = ExecutionStep(step_name='final_select', sql='-- rendered by UnifiedSqlBuilderV2', step_type='final_select')
        return plan

    def _shape_from_result(self, result: FeatureLineageResult) -> QueryShape:
        parse_result = self.sql_parser.parse_feature(result.feature_spec)
        root = parse_result.expression
        if root is None:
            raise ValueError(f"Unable to parse expression for feature '{result.feature_spec.feature_name}'")

        with_sql = self._clause_sql(root.args.get('with'), result.feature_spec.dialect)
        from_sql = self._clause_sql(root.args.get('from'), result.feature_spec.dialect)
        joins = tuple(self._clause_sql(join, result.feature_spec.dialect) for join in (root.args.get('joins') or []))
        where_sql = self._clause_sql(root.args.get('where'), result.feature_spec.dialect)
        group_sql = self._clause_sql(root.args.get('group'), result.feature_spec.dialect)
        having_sql = self._clause_sql(root.args.get('having'), result.feature_spec.dialect)
        qualify_sql = self._clause_sql(root.args.get('qualify'), result.feature_spec.dialect)

        entity_expr_sql = self._find_select_expression_sql(root, result.feature_spec.entity_key, result.feature_spec.dialect)
        final_expr_sql = self._find_select_expression_sql(root, result.feature_spec.final_alias, result.feature_spec.dialect)

        return QueryShape(
            feature_name=result.feature_spec.feature_name,
            entity_key=result.feature_spec.entity_key,
            entity_expr_sql=entity_expr_sql,
            final_alias=result.feature_spec.final_alias,
            final_expr_sql=final_expr_sql,
            with_sql=with_sql,
            from_sql=from_sql,
            joins_sql=joins,
            where_sql=where_sql,
            group_sql=group_sql,
            having_sql=having_sql,
            qualify_sql=qualify_sql,
        )

    def _find_select_expression_sql(self, root_expression, alias_name: str, dialect: str) -> str:
        select_items = getattr(root_expression, 'expressions', []) or []
        for item in select_items:
            if getattr(item, 'alias_or_name', None) == alias_name:
                expression = item.this if isinstance(item, exp.Alias) else item
                return self.normalizer.normalize_expression_sql(expression, dialect)
            if isinstance(item, exp.Column) and item.name == alias_name:
                return self.normalizer.normalize_expression_sql(item, dialect)
        return alias_name

    def _build_group_cte_sql(self, shapes: list[QueryShape]) -> str:
        first = shapes[0]
        select_lines = [f"{first.entity_expr_sql} AS {first.entity_key}"]
        for shape in shapes:
            select_lines.append(f"{shape.final_expr_sql} AS {shape.final_alias}")

        parts: list[str] = []
        if first.with_sql:
            parts.append(first.with_sql)
        parts.append('SELECT')
        parts.append('    ' + ',\n    '.join(select_lines))
        if first.from_sql:
            parts.append(first.from_sql)
        if first.joins_sql:
            parts.extend(first.joins_sql)
        if first.where_sql:
            parts.append(first.where_sql)
        if first.group_sql:
            parts.append(first.group_sql)
        if first.having_sql:
            parts.append(first.having_sql)
        if first.qualify_sql:
            parts.append(first.qualify_sql)
        return '\n'.join(parts)

    def _build_entity_sql(self, entity_key: str, step_names: list[str]) -> str:
        if not step_names:
            return f"SELECT NULL AS {entity_key} WHERE 1 = 0"
        selects = [f"SELECT DISTINCT {entity_key} FROM {step_name}" for step_name in step_names]
        return '\nUNION\n'.join(selects)

    def _step_name(self, prefix: str, signature: tuple, idx: int) -> str:
        digest = md5(repr(signature).encode('utf-8')).hexdigest()[:10]
        return f"{prefix}_{idx}_{digest}"

    def _clause_sql(self, expression, dialect: str) -> str:
        if expression is None:
            return ''
        return self.normalizer.normalize_expression_sql(expression, dialect)
