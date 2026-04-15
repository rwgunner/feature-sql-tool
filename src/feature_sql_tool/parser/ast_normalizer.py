from __future__ import annotations

from typing import Any


class AstNormalizer:
    def normalize_expression_sql(self, expression: Any, dialect: str) -> str:
        try:
            return expression.sql(dialect=dialect, pretty=False)
        except Exception:
            return str(expression)
