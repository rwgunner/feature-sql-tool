from __future__ import annotations

from typing import Any


class AstNormalizer:
    """Normalizes AST expressions into canonical SQL strings."""

    def normalize_expression_sql(self, expression: Any, dialect: str) -> str:
        try:
            return expression.sql(dialect=dialect, pretty=False)
        except Exception:
            return str(expression)
