from __future__ import annotations

from sqlglot import exp


class ExpressionExpander:
    def collect_columns(self, expression):
        if expression is None:
            return []
        return list(expression.find_all(exp.Column))
