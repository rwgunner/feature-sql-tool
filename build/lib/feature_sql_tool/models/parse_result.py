from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .feature_spec import FeatureSpec


@dataclass
class ParseResult:
    feature_spec: FeatureSpec
    raw_sql: str
    expression: Any
    scope_registry: Any
