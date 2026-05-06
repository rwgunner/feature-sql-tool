from __future__ import annotations

from sqlglot import exp


class FilterDependencyCollector:
    def collect(self, expression):
        result = {
            'where': [],
            'having': [],
            'qualify': [],
            'join_on': [],
        }
        if expression is None:
            return result

        for key in ('where', 'having', 'qualify'):
            clause = expression.args.get(key)
            if clause is not None:
                result[key] = list(clause.find_all(exp.Column))

        joins = expression.args.get('joins') or []
        for join in joins:
            on_expr = join.args.get('on')
            if on_expr is not None:
                result['join_on'].extend(list(on_expr.find_all(exp.Column)))

        return result
