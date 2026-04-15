from __future__ import annotations

import json
from dataclasses import asdict

from feature_sql_tool.models.lineage_result import FeatureLineageResult


class LineageReporterV2:
    def to_json(self, result: FeatureLineageResult) -> str:
        return json.dumps(asdict(result), ensure_ascii=False, indent=2, default=str)
