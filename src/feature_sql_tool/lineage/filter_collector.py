from __future__ import annotations

from typing import Any, Dict, List

from sqlglot import exp

from feature_sql_tool.lineage.expression_dependencies import ExpressionDependencyExtractor


class FilterDependencyCollector:
    def __init__(self) -> None:
        self.column_extractor = ExpressionDependencyExtractor()

    def collect(self, scope_expression: Any) -> Dict[str, List[exp.Column]]:
        """Collect columns from filter-like clauses in the current scope."""
        result: Dict[str, List[exp.Column]] = {
            "where": [],
            "having": [],
            "qualify": [],
            "join_on": [],
        }

        if scope_expression is None:
            return result

        where_expr = scope_expression.args.get("where")
        having_expr = scope_expression.args.get("having")
        qualify_expr = scope_expression.args.get("qualify")

        if where_expr:
            result["where"] = self.column_extractor.extract_columns(where_expr)
        if having_expr:
            result["having"] = self.column_extractor.extract_columns(having_expr)
        if qualify_expr:
            result["qualify"] = self.column_extractor.extract_columns(qualify_expr)

        for join in scope_expression.find_all(exp.Join):
            on_expr = join.args.get("on")
            if on_expr:
                result["join_on"].extend(self.column_extractor.extract_columns(on_expr))

        return result
