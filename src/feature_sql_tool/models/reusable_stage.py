from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReusableStage:
    reusable_stage_id: str
    reusable_name: str
    stage_type: str
    input_stage_names: tuple[str, ...] = field(default_factory=tuple)
    output_columns: tuple[str, ...] = field(default_factory=tuple)
    group_keys: tuple[str, ...] = field(default_factory=tuple)
    source_tables: tuple[str, ...] = field(default_factory=tuple)
    join_signatures: tuple[str, ...] = field(default_factory=tuple)
    filter_signatures: tuple[str, ...] = field(default_factory=tuple)
    expression_signatures: tuple[str, ...] = field(default_factory=tuple)
    select_items: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    from_sql: str = ''
    joins_sql: tuple[str, ...] = field(default_factory=tuple)
    where_sql: str = ''
    group_sql: str = ''
    having_sql: str = ''
    qualify_sql: str = ''
    raw_sql: str = ''
    feature_names: tuple[str, ...] = field(default_factory=tuple)
