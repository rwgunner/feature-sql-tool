from __future__ import annotations

from collections import defaultdict

from feature_sql_tool.models.query_plan import FeatureQueryPlan
from feature_sql_tool.models.query_stage import QueryStage
from feature_sql_tool.models.reusable_stage import ReusableStage
from feature_sql_tool.planner.node_canonicalizer import NodeCanonicalizer


class AggregateMerger:
    def __init__(self) -> None:
        self.canonicalizer = NodeCanonicalizer()

    def merge_aggregate_stages(
        self,
        plans: list[FeatureQueryPlan],
        base_stage_mapping: dict[tuple[str, str], str],
    ) -> tuple[list[ReusableStage], dict[tuple[str, str], str]]:
        grouped: dict[tuple, list[tuple[str, QueryStage, str]]] = defaultdict(list)
        for plan in plans:
            for stage in plan.stages:
                if stage.stage_type != 'aggregation':
                    continue
                upstream_name = stage.input_stage_names[0] if stage.input_stage_names else ''
                upstream_reusable = base_stage_mapping.get((plan.feature_name, upstream_name), upstream_name)
                sig = self.canonicalizer.aggregate_signature(stage, upstream_reusable)
                grouped[sig].append((plan.feature_name, stage, upstream_reusable))

        reusable: list[ReusableStage] = []
        stage_mapping: dict[tuple[str, str], str] = {}
        for idx, (signature, entries) in enumerate(grouped.items(), start=1):
            _, first_stage, upstream_name = entries[0]
            digest = self.canonicalizer.digest(signature)
            name = f'agg_{idx}_{digest}'
            select_items_map: dict[str, str] = {}
            for _, stage, _ in entries:
                for alias, expr in stage.select_items:
                    if alias not in select_items_map:
                        select_items_map[alias] = expr

            select_items: list[tuple[str, str]] = []
            group_key_aliases = set()
            for group_expr in first_stage.group_keys:
                alias = group_expr.split('.')[-1].replace('`', '')
                group_key_aliases.add(alias)
                select_items.append((alias, group_expr))
            for alias, expr in sorted(select_items_map.items()):
                if alias in group_key_aliases:
                    continue
                select_items.append((alias, expr))
            raw_sql = self._render_stage(first_stage, upstream_name, select_items)
            reusable_stage = ReusableStage(
                reusable_stage_id=f'reusable::{name}',
                reusable_name=name,
                stage_type='aggregation',
                input_stage_names=(upstream_name,),
                output_columns=tuple(alias for alias, _ in select_items),
                group_keys=first_stage.group_keys,
                source_tables=first_stage.source_tables,
                join_signatures=first_stage.join_signatures,
                filter_signatures=first_stage.filter_signatures,
                expression_signatures=tuple(expr for _, expr in select_items),
                select_items=tuple(select_items),
                from_sql=f'FROM {upstream_name}',
                where_sql=first_stage.where_sql,
                group_sql=first_stage.group_sql,
                having_sql=first_stage.having_sql,
                qualify_sql=first_stage.qualify_sql,
                raw_sql=raw_sql,
                feature_names=tuple(sorted({feat for feat, _, _ in entries})),
            )
            reusable.append(reusable_stage)
            for feature_name, stage, _ in entries:
                stage_mapping[(feature_name, stage.stage_name)] = name
        return reusable, stage_mapping

    def _render_stage(self, stage: QueryStage, upstream_name: str, select_items: list[tuple[str, str]]) -> str:
        lines = ['SELECT', '    ' + ',\n    '.join(f"{expr} AS {alias}" for alias, expr in select_items), f'FROM {upstream_name}']
        if stage.where_sql:
            lines.append(stage.where_sql)
        if stage.group_sql:
            lines.append(stage.group_sql)
        if stage.having_sql:
            lines.append(stage.having_sql)
        if stage.qualify_sql:
            lines.append(stage.qualify_sql)
        return '\n'.join(lines)
