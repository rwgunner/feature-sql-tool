from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ExpressionRef:
    scope_name: str
    alias_name: str
    expression: Any
    expression_sql: str
    is_computed: bool
    is_passthrough: bool
    passthrough_column: Optional[Any] = None
