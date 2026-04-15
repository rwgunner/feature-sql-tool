from __future__ import annotations

from typing import Optional

from sqlglot import exp


class PassthroughDetector:
    def is_passthrough(self, expression) -> bool:
        return self.extract_passthrough_column(expression) is not None

    def extract_passthrough_column(self, expression) -> Optional[exp.Column]:
        if isinstance(expression, exp.Alias):
            expression = expression.this
        if isinstance(expression, exp.Column):
            return expression
        return None
