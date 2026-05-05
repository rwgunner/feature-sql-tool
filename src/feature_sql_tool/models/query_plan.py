from __future__ import annotations

from dataclasses import dataclass

from .query_stage import QueryStage


@dataclass(frozen=True)
class FeatureQueryPlan:
    feature_name: str
    entity_keys: tuple[str, ...]
    stages: tuple[QueryStage, ...]
    final_stage_name: str

    def stage_by_name(self, stage_name: str) -> QueryStage:
        for stage in self.stages:
            if stage.stage_name == stage_name:
                return stage
        raise KeyError(stage_name)
