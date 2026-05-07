from __future__ import annotations

import re

from feature_sql_tool.models.execution_plan import ExecutionPlan


class ReusablePlanValidationError(Exception):
    pass


class ReusablePlanValidator:
    def validate(self, plan: ExecutionPlan) -> None:
        known = {step.step_name for step in list(plan.base_steps) + list(plan.aggregate_steps)}
        for step in list(plan.base_steps) + list(plan.aggregate_steps):
            sql = (step.sql or '').strip()
            if not sql:
                raise ReusablePlanValidationError(f"Stage {step.step_name!r} has empty SQL")
            if re.search(r'SELECT\s*(FROM|\))', sql, flags=re.IGNORECASE | re.MULTILINE):
                raise ReusablePlanValidationError(f"Stage {step.step_name!r} produced empty SELECT")

            aliases = set(re.findall(r'\b(?:FROM|JOIN)\s+[^\s,()]+\s+AS\s+(\w+)', sql, flags=re.IGNORECASE))
            dotted = set(re.findall(r'\b(\w+)\.', sql))
            keywords = {
                'CAST', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'COUNT', 'SUM', 'MAX', 'MIN', 'COALESCE',
                'DISTINCT', 'FROM', 'JOIN', 'LEFT', 'RIGHT', 'ON', 'WHERE', 'GROUP', 'BY', 'HAVING',
                'QUALIFY', 'AS', 'SELECT', 'AND', 'OR'
            }
            bad_aliases = {a for a in dotted if a.upper() not in keywords and a not in aliases and a != step.step_name}
            if bad_aliases:
                raise ReusablePlanValidationError(
                    f"Stage {step.step_name!r} references aliases not bound in FROM/JOIN: {sorted(bad_aliases)}"
                )

            refs = set(re.findall(r'\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)\b', sql, flags=re.IGNORECASE))
            dangling = {r for r in refs if r.startswith(('base_', 'agg_')) and r not in known and r != step.step_name}
            if dangling:
                raise ReusablePlanValidationError(
                    f"Stage {step.step_name!r} references unknown reusable stages: {sorted(dangling)}"
                )
