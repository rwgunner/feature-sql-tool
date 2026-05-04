from __future__ import annotations

from collections import defaultdict

from feature_sql_tool.models.query_plan import FeatureQueryPlan
from feature_sql_tool.models.query_stage import QueryStage
from feature_sql_tool.models.reusable_stage import ReusableStage
from feature_sql_tool.planner.node_canonicalizer import NodeCanonicalizer


class CommonSubgraphMerger:
    def __init__(self) -> None:
        self.canonicalizer = NodeCanonicalizer()

    def merge_base_stages(
        self,
        plans: list[FeatureQueryPlan],
        required_columns: dict[tuple, set[tuple[str, str]]],
    ) -> tuple[list[ReusableStage], dict[tuple[str, str], str], dict[str, str]]:
        grouped: dict[tuple, list[tuple[str, QueryStage]]] = defaultdict(list)
        for plan in plans:
            for stage in plan.stages:
                if stage.stage_type == 'source_projection':
                    grouped[self.canonicalizer.base_signature(stage)].append((plan.feature_name, stage))

        reusable: list[ReusableStage] = []
        stage_mapping: dict[tuple[str, str], str] = {}
        signature_to_name: dict[str, str] = {}
        for idx, (signature, entries) in enumerate(grouped.items(), start=1):
            _, first_stage = entries[0]
            digest = self.canonicalizer.digest(signature)
            name = f'base_{idx}_{digest}'
            select_items = sorted(required_columns.get(signature, set(first_stage.select_items)), key=lambda x: x[0])
            raw_sql = self._render_stage(first_stage, select_items)
            reusable_stage = ReusableStage(
                reusable_stage_id=f'reusable::{name}',
                reusable_name=name,
                stage_type='source_projection',
                input_stage_names=first_stage.input_stage_names,
                output_columns=tuple(alias for alias, _ in select_items),
                source_tables=first_stage.source_tables,
                join_signatures=first_stage.join_signatures,
                filter_signatures=first_stage.filter_signatures,
                expression_signatures=tuple(expr for _, expr in select_items),
                select_items=tuple(select_items),
                from_sql=first_stage.from_sql,
                joins_sql=first_stage.joins_sql,
                where_sql=first_stage.where_sql,
                raw_sql=raw_sql,
                feature_names=tuple(sorted({feat for feat, _ in entries})),
            )
            reusable.append(reusable_stage)
            signature_to_name[repr(signature)] = name
            for feature_name, stage in entries:
                stage_mapping[(feature_name, stage.stage_name)] = name
        return reusable, stage_mapping, signature_to_name

    def _render_stage(self, stage: QueryStage, select_items: list[tuple[str, str]]) -> str:
        lines = ['SELECT', '    ' + ',\n    '.join(f"{expr} AS {alias}" for alias, expr in select_items)]
        if stage.from_sql:
            lines.append(stage.from_sql)
        if stage.joins_sql:
            lines.extend(stage.joins_sql)
        if stage.where_sql:
            lines.append(stage.where_sql)
        return '\n'.join(lines)
