from __future__ import annotations

from feature_sql_tool.generator.unified_sql_builder_v2 import UnifiedSqlBuilderV2
from feature_sql_tool.graph.unified_graph_builder import UnifiedFeatureGraphBuilder
from feature_sql_tool.lineage.extractor_v2 import FeatureLineageExtractorV2
from feature_sql_tool.models.vector_build_request import VectorBuildRequest
from feature_sql_tool.planner.execution_planner_v2 import ExecutionPlannerV2
from feature_sql_tool.planner.reusable_subgraph_detector import ReusableSubgraphDetector
from feature_sql_tool.reporting.optimization_reporter import OptimizationReporter


class FeatureSqlToolV2:
    def __init__(self) -> None:
        self.extractor = FeatureLineageExtractorV2()
        self.unified_builder = UnifiedFeatureGraphBuilder()
        self.planner = ExecutionPlannerV2()
        self.sql_builder = UnifiedSqlBuilderV2()
        self.reusable_detector = ReusableSubgraphDetector()
        self.optimization_reporter = OptimizationReporter()

    def analyze_features(self, features):
        return [self.extractor.extract(feature) for feature in features]

    def build_unified_graph(self, features):
        results = self.analyze_features(features)
        return self.unified_builder.build(results)

    def build_execution_plan(self, request: VectorBuildRequest):
        results = self.analyze_features(request.features)
        return self.planner.build_plan(results, request)

    def build_unified_sql(self, request: VectorBuildRequest) -> str:
        plan = self.build_execution_plan(request)
        return self.sql_builder.build(request, plan)

    def build_optimization_report(self, request: VectorBuildRequest) -> str:
        results = self.analyze_features(request.features)
        unified_graph = self.unified_builder.build(results)
        reusable = self.reusable_detector.detect(unified_graph)
        plan = self.planner.build_plan(results, request)
        return self.optimization_reporter.to_json(plan, reusable)
