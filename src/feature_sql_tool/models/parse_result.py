from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from feature_sql_tool.models.feature_spec import FeatureSpec


@dataclass
class ParseResult:
    """Result of parsing a single SQL feature file."""

    feature_spec: FeatureSpec
    raw_sql: str
    expression: Any
    scope_registry: Any
