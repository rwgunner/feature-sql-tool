from __future__ import annotations

from typing import Iterable, List

from feature_sql_tool.generator.unified_sql_builder import UnifiedSqlBuilder
from feature_sql_tool.graph.merger import FeatureGraphMerger
from feature_sql_tool.lineage.extractor import FeatureLineageExtractor
from feature_sql_tool.models.execution_plan import ExecutionPlan
from feature_sql_tool.models.feature_spec import FeatureSpec
from feature_sql_tool.models.lineage_result import FeatureLineageResult
from feature_sql_tool.planner.execution_planner import ExecutionPlanner


class FeatureSqlTool:
    def __init__(self) -> None:
        self.extractor = FeatureLineageExtractor()
        self.merger = FeatureGraphMerger()
        self.planner = ExecutionPlanner()
        self.sql_builder = UnifiedSqlBuilder()

    def analyze_features(self, feature_specs: Iterable[FeatureSpec]) -> List[FeatureLineageResult]:
        return [self.extractor.extract(spec) for spec in feature_specs]

    def build_execution_plan(self, feature_specs: Iterable[FeatureSpec]) -> ExecutionPlan:
        results = self.analyze_features(feature_specs)
        return self.planner.build_plan(results)

    def build_unified_sql(self, feature_specs: Iterable[FeatureSpec]) -> str:
        specs = list(feature_specs)
        plan = self.build_execution_plan(specs)
        return self.sql_builder.build(specs, plan)
