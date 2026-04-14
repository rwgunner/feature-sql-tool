from __future__ import annotations

from typing import Any, List

from sqlglot import exp


class ExpressionDependencyExtractor:
    """Extracts column references from an arbitrary SQL expression."""

    def extract_columns(self, expression: Any) -> List[exp.Column]:
        if expression is None:
            return []
        return list(expression.find_all(exp.Column))
