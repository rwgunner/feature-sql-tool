from __future__ import annotations

from hashlib import md5

from feature_sql_tool.models.query_stage import QueryStage


class NodeCanonicalizer:
    def base_signature(self, stage: QueryStage) -> tuple:
        return (
            stage.stage_type,
            tuple(stage.source_tables),
            tuple(stage.join_signatures),
            tuple(stage.filter_signatures),
        )

    def aggregate_signature(self, stage: QueryStage, upstream_signature: str) -> tuple:
        return (
            stage.stage_type,
            upstream_signature,
            tuple(stage.group_keys),
            tuple(stage.filter_signatures),
        )

    def digest(self, signature: tuple) -> str:
        return md5(repr(signature).encode('utf-8')).hexdigest()[:10]
