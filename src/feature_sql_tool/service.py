from __future__ import annotations

from collections.abc import Iterable

from feature_sql_tool.generator.unified_sql_builder import UnifiedSqlBuilder
from feature_sql_tool.graph.unified_graph_builder import UnifiedFeatureGraphBuilder
from feature_sql_tool.lineage.extractor import FeatureLineageExtractor
from feature_sql_tool.models.feature_spec import FeatureSpec
from feature_sql_tool.models.vector_build_request import VectorBuildRequest
from feature_sql_tool.planner.execution_planner import ExecutionPlanner
from feature_sql_tool.planner.reusable_subgraph_detector import ReusableSubgraphDetector
from feature_sql_tool.reporting.optimization_reporter import OptimizationReporter


class FeatureSqlTool:
    def __init__(self) -> None:
        self.extractor = FeatureLineageExtractor()
        self.unified_builder = UnifiedFeatureGraphBuilder()
        self.planner = ExecutionPlanner()
        self.sql_builder = UnifiedSqlBuilder()
        self.reusable_detector = ReusableSubgraphDetector()
        self.optimization_reporter = OptimizationReporter()

    def _validate_same_entity_keys(self, features: list[FeatureSpec], method_name: str) -> tuple[str, ...]:
        if not features:
            raise ValueError('No features provided.')
        entity_key_sets = {tuple(feature.entity_keys or (feature.entity_key,)) for feature in features}
        if len(entity_key_sets) != 1:
            raise ValueError(f'All features passed to {method_name} must share the same entity_keys, got: {sorted(entity_key_sets)}')
        return next(iter(entity_key_sets))

    def analyze_features(self, features: Iterable[FeatureSpec]):
        feature_list = list(features)
        self._validate_same_entity_keys(feature_list, 'analyze_features')
        return [self.extractor.extract(feature) for feature in feature_list]

    def build_unified_graph(self, features: Iterable[FeatureSpec]):
        results = self.analyze_features(features)
        return self.unified_builder.build(results)

    def _ensure_request(self, request_or_features) -> VectorBuildRequest:
        if isinstance(request_or_features, VectorBuildRequest):
            features = list(request_or_features.features)
            entity_keys = self._validate_same_entity_keys(features, 'build_unified_sql')
            if tuple(request_or_features.entity_keys or (request_or_features.entity_key,)) != entity_keys:
                raise ValueError(f"VectorBuildRequest.entity_keys {tuple(request_or_features.entity_keys or ())} do not match feature entity_keys {entity_keys}")
            return request_or_features
        features = list(request_or_features)
        entity_keys = self._validate_same_entity_keys(features, 'build_unified_sql')
        dialects = {feature.dialect for feature in features}
        dialect = next(iter(dialects)) if dialects else 'spark'
        return VectorBuildRequest(features=features, entity_key=entity_keys[0], entity_keys=entity_keys, entity_sql_file_path=None, dialect=dialect)

    def build_execution_plan(self, request_or_features):
        request = self._ensure_request(request_or_features)
        if len(request.entity_keys or ()) > 1:
            raise NotImplementedError('Unified SQL generation for composite entity_keys is not implemented yet. Use analyze_features/build_unified_graph for composite-key features.')
        results = self.analyze_features(request.features)
        return self.planner.build_plan(results, request)

    def build_unified_sql(self, request_or_features) -> str:
        request = self._ensure_request(request_or_features)
        if len(request.entity_keys or ()) > 1:
            raise NotImplementedError('Unified SQL generation for composite entity_keys is not implemented yet. Use analyze_features/build_unified_graph for composite-key features.')
        plan = self.build_execution_plan(request)
        return self.sql_builder.build(request, plan)

    def build_optimization_report(self, request_or_features) -> str:
        request = self._ensure_request(request_or_features)
        if len(request.entity_keys or ()) > 1:
            raise NotImplementedError('Optimization report for composite entity_keys is not implemented yet.')
        results = self.analyze_features(request.features)
        unified_graph = self.unified_builder.build(results)
        reusable = self.reusable_detector.detect(unified_graph)
        plan = self.planner.build_plan(results, request)
        return self.optimization_reporter.to_json(plan, reusable)
