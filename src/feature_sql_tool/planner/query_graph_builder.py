from __future__ import annotations

from typing import Any

from sqlglot import exp

from feature_sql_tool.models.feature_spec import FeatureSpec
from feature_sql_tool.models.query_plan import FeatureQueryPlan
from feature_sql_tool.models.query_stage import QueryStage
from feature_sql_tool.parser.ast_normalizer import AstNormalizer
from feature_sql_tool.parser.sql_parser import SqlParser


class QueryGraphBuilder:
    def __init__(self) -> None:
        self.parser = SqlParser()
        self.normalizer = AstNormalizer()

    def build(self, feature_spec: FeatureSpec) -> FeatureQueryPlan:
        parse_result = self.parser.parse_feature(feature_spec)
        root = parse_result.expression
        if root is None:
            raise ValueError(f"Unable to parse expression for feature '{feature_spec.feature_name}'")

        stages: list[QueryStage] = []
        cte_names: list[str] = []
        with_expr = root.args.get('with')
        for idx, cte in enumerate(getattr(with_expr, 'expressions', []) or []):
            cte_name = getattr(cte, 'alias_or_name', None) or f'cte_{idx}'
            cte_names.append(cte_name)
            query_expr = cte.this
            stages.append(self._build_stage(feature_spec, cte_name, query_expr, cte_names[:-1]))

        final_stage_name = f"{feature_spec.feature_name}__final"
        stages.append(self._build_stage(feature_spec, final_stage_name, root, cte_names, final_stage=True))
        return FeatureQueryPlan(
            feature_name=feature_spec.feature_name,
            entity_keys=tuple(feature_spec.entity_keys or ()),
            stages=tuple(stages),
            final_stage_name=final_stage_name,
        )

    def _build_stage(self, feature_spec: FeatureSpec, stage_name: str, expression: Any, prior_cte_names: list[str], final_stage: bool = False) -> QueryStage:
        select_expr = self._unwrap_query(expression)
        select_items = self._select_items(select_expr, feature_spec.dialect)
        output_columns = tuple(alias for alias, _ in select_items)
        group_expr = getattr(select_expr, 'args', {}).get('group')
        group_keys = tuple(self.normalizer.normalize_expression_sql(item, feature_spec.dialect) for item in getattr(group_expr, 'expressions', []) or [])
        source_tables = tuple(sorted({table.name for table in select_expr.find_all(exp.Table) if table.name not in prior_cte_names}))
        joins = tuple(self.normalizer.normalize_expression_sql(join, feature_spec.dialect) for join in (select_expr.args.get('joins') or []))
        filters = []
        for clause_name in ('where', 'having', 'qualify'):
            clause = select_expr.args.get(clause_name)
            if clause is not None:
                filters.append(self.normalizer.normalize_expression_sql(clause, feature_spec.dialect))
        expression_signatures = tuple(sql for _, sql in select_items)
        input_stage_names = tuple(sorted({table.name for table in select_expr.find_all(exp.Table) if table.name in prior_cte_names}))
        stage_type = 'final_projection' if final_stage else ('aggregation' if group_keys else 'source_projection')
        return QueryStage(
            stage_id=f"{feature_spec.feature_name}::{stage_name}",
            stage_name=stage_name,
            stage_type=stage_type,
            input_stage_names=input_stage_names,
            output_columns=output_columns,
            group_keys=group_keys,
            source_tables=source_tables,
            join_signatures=joins,
            filter_signatures=tuple(filters),
            expression_signatures=expression_signatures,
            select_items=tuple(select_items),
            from_sql=self._clause_sql(select_expr.args.get('from'), feature_spec.dialect),
            joins_sql=joins,
            where_sql=self._clause_sql(select_expr.args.get('where'), feature_spec.dialect),
            group_sql=self._clause_sql(select_expr.args.get('group'), feature_spec.dialect),
            having_sql=self._clause_sql(select_expr.args.get('having'), feature_spec.dialect),
            qualify_sql=self._clause_sql(select_expr.args.get('qualify'), feature_spec.dialect),
            raw_sql=self.normalizer.normalize_expression_sql(select_expr, feature_spec.dialect),
        )

    def _unwrap_query(self, expression: Any):
        if isinstance(expression, exp.CTE):
            return self._unwrap_query(expression.this)
        if isinstance(expression, exp.Subquery):
            return self._unwrap_query(expression.this)
        return expression

    def _select_items(self, expression: Any, dialect: str) -> list[tuple[str, str]]:
        target = expression
        if isinstance(expression, exp.SetOperation):
            target = expression.left
        items = []
        for idx, item in enumerate(getattr(target, 'expressions', []) or []):
            alias = getattr(item, 'alias_or_name', None)
            if not alias:
                if isinstance(item, exp.Column):
                    alias = item.name
                else:
                    alias = f'__col_{idx}'
            expr = item.this if isinstance(item, exp.Alias) else item
            items.append((alias, self.normalizer.normalize_expression_sql(expr, dialect)))
        return items

    def _clause_sql(self, expression: Any, dialect: str) -> str:
        if expression is None:
            return ''
        return self.normalizer.normalize_expression_sql(expression, dialect)
