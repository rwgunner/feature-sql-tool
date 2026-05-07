
from __future__ import annotations

import re
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from hashlib import md5

from feature_sql_tool.models.execution_plan import ExecutionPlan, ExecutionStep
from feature_sql_tool.models.vector_build_request import VectorBuildRequest


@dataclass(frozen=True)
class _ParsedFeatureStep:
    feature_name: str
    original_step_name: str
    cte1_name: str
    cte1_body: str
    cte2_name: str
    cte2_body: str
    entity_select_items: list[str]
    feature_select_item: str
    final_from_sql: str
    cte1_select_items: list[str]
    cte1_from_sql: str
    cte1_where_sql: str
    cte2_select_items: list[str]
    cte2_from_name: str
    cte2_group_items: list[str]


@dataclass(frozen=True)
class _ParsedCteChainFeatureStep:
    feature_name: str
    original_step_name: str
    ctes: list[tuple[str, str]]
    entity_select_items: list[str]
    feature_select_item: str
    final_from_sql: str
    agg_select_items: list[str]
    agg_from_sql: str
    agg_where_sql: str
    agg_group_items: list[str]

    @property
    def agg_cte_name(self) -> str:
        return self.ctes[-1][0]

    @property
    def prefix_cte_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.ctes[:-1])


class SimpleReuseOptimizer:
    """Optimizer for reusable SQL fragments shared by multiple feature SQL files.

    The first generation of this optimizer handled a narrow pattern only:
    ``WITH base AS (...), agg AS (...) SELECT ...``.  Version 2.5.0 keeps that
    path, but also recognizes longer CTE chains such as::

        WITH cte_a AS (... UNION ALL ...),
             cte_b AS (... FROM cte_a ...),
             base AS (... FROM cte_b ...),
             agg AS (... FROM base GROUP BY keys)
        SELECT keys..., feature FROM agg

    When several features share the same chain shape, the optimizer emits one
    reusable chain and one merged aggregate CTE, then projects each feature from
    that merged aggregate.  For intentionally similar chains where one feature
    needs extra passthrough columns, the reusable CTE body is chosen from the
    richest candidate for that CTE name.  This gives a safe high-reuse baseline:
    read/prepare once, aggregate once, project many features.
    """

    def optimize(self, request: VectorBuildRequest, plan: ExecutionPlan) -> ExecutionPlan | None:
        return self._optimize_cte_chains(request, plan) or self._optimize_simple_two_cte(request, plan)

    def _optimize_simple_two_cte(self, request: VectorBuildRequest, plan: ExecutionPlan) -> ExecutionPlan | None:
        parsed: list[_ParsedFeatureStep] = []
        for feature in request.features:
            steps = plan.feature_steps.get(feature.feature_name, [])
            if len(steps) != 1:
                continue
            parsed_step = self._try_parse_feature_step(feature.feature_name, steps[0], len(request.entity_keys or (request.entity_key,)))
            if parsed_step is not None:
                parsed.append(parsed_step)

        groups: dict[tuple[str, str, str, str, str], list[_ParsedFeatureStep]] = {}
        for item in parsed:
            signature = (
                item.cte1_from_sql,
                item.cte1_where_sql,
                item.cte2_from_name,
                ' | '.join(item.cte2_group_items),
                item.final_from_sql.replace(item.cte2_name, '__AGG__'),
            )
            groups.setdefault(signature, []).append(item)

        eligible_groups = [group for group in groups.values() if len(group) >= 2]
        if not eligible_groups:
            return None

        new_plan = deepcopy(plan)
        changed = False
        for group in eligible_groups:
            merged = self._build_group_steps(group)
            if merged is None:
                continue
            base_step, agg_step, feature_steps = merged
            changed = True

            for item in group:
                new_plan.feature_steps[item.feature_name] = [feature_steps[item.feature_name]]
                new_plan.feature_to_step_name[item.feature_name] = feature_steps[item.feature_name].step_name
                new_plan.feature_to_column_name[item.feature_name] = item.feature_name

            old_names = {item.original_step_name for item in group}
            new_plan.base_steps = [s for s in new_plan.base_steps if s.step_name not in old_names]
            new_plan.aggregate_steps = [s for s in new_plan.aggregate_steps if s.step_name not in old_names]
            new_plan.reusable_steps = [s for s in new_plan.reusable_steps if s.step_name not in old_names]
            new_plan.base_steps.append(base_step)
            new_plan.aggregate_steps.append(agg_step)

        return self._finalize_if_changed(request, new_plan, changed)

    def _optimize_cte_chains(self, request: VectorBuildRequest, plan: ExecutionPlan) -> ExecutionPlan | None:
        entity_key_count = len(request.entity_keys or (request.entity_key,))
        parsed: list[_ParsedCteChainFeatureStep] = []
        for feature in request.features:
            steps = plan.feature_steps.get(feature.feature_name, [])
            if len(steps) != 1:
                continue
            parsed_step = self._try_parse_cte_chain_feature_step(feature.feature_name, steps[0], entity_key_count)
            if parsed_step is not None:
                parsed.append(parsed_step)

        groups: dict[tuple, list[_ParsedCteChainFeatureStep]] = {}
        for item in parsed:
            signature = (
                item.prefix_cte_names,
                self._normalize_from_source(item.agg_from_sql, item.prefix_cte_names),
                ' | '.join(item.agg_group_items),
                item.final_from_sql.replace(item.agg_cte_name, '__AGG__'),
            )
            groups.setdefault(signature, []).append(item)

        eligible_groups = [group for group in groups.values() if len(group) >= 2]
        if not eligible_groups:
            return None

        new_plan = deepcopy(plan)
        changed = False
        for group in eligible_groups:
            merged = self._build_cte_chain_group_steps(group)
            if merged is None:
                continue
            reusable_steps, agg_step, feature_steps = merged
            changed = True

            for item in group:
                new_plan.feature_steps[item.feature_name] = [feature_steps[item.feature_name]]
                new_plan.feature_to_step_name[item.feature_name] = feature_steps[item.feature_name].step_name
                new_plan.feature_to_column_name[item.feature_name] = item.feature_name

            old_names = {item.original_step_name for item in group}
            new_plan.base_steps = [s for s in new_plan.base_steps if s.step_name not in old_names]
            new_plan.aggregate_steps = [s for s in new_plan.aggregate_steps if s.step_name not in old_names]
            new_plan.reusable_steps = [s for s in new_plan.reusable_steps if s.step_name not in old_names]
            new_plan.reusable_steps.extend(reusable_steps)
            new_plan.aggregate_steps.append(agg_step)

        return self._finalize_if_changed(request, new_plan, changed)

    def _finalize_if_changed(self, request: VectorBuildRequest, plan: ExecutionPlan, changed: bool) -> ExecutionPlan | None:
        if not changed:
            return None
        if request.entity_sql_file_path is None and plan.feature_to_step_name:
            selects = [
                f"SELECT DISTINCT {', '.join(request.entity_keys or (request.entity_key,))} FROM {step_name}"
                for step_name in dict.fromkeys(plan.feature_to_step_name.values())
            ]
            plan.entity_step = ExecutionStep('entity_base', '\nUNION\n'.join(selects), 'entity')
        return plan

    def _build_cte_chain_group_steps(self, group: list[_ParsedCteChainFeatureStep]):
        first = group[0]
        prefix_names = list(first.prefix_cte_names)
        rename_map = {
            name: self._step_name(f"reuse_{self._safe_identifier(name)}", [item.feature_name for item in group], name)
            for name in prefix_names
        }
        agg_name = self._step_name('agg_reuse', [item.feature_name for item in group], first.ctes[-1][1])

        reusable_steps: list[ExecutionStep] = []
        for idx, original_name in enumerate(prefix_names):
            candidate_bodies = [item.ctes[idx][1] for item in group]
            chosen_body = self._choose_richest_cte_body(candidate_bodies)
            rewritten_body = self._replace_identifiers(chosen_body, rename_map)
            reusable_steps.append(ExecutionStep(rename_map[original_name], rewritten_body, 'reusable_cte'))

        group_key_selects: list[str] = []
        for select_item in first.agg_select_items:
            item_no_alias = self._strip_alias(select_item)
            if select_item in first.agg_group_items or item_no_alias in first.agg_group_items:
                group_key_selects.append(select_item)
        agg_exprs: list[str] = []
        for item in group:
            for select_item in item.agg_select_items:
                item_no_alias = self._strip_alias(select_item)
                if select_item in group_key_selects or item_no_alias in first.agg_group_items:
                    continue
                if select_item not in agg_exprs:
                    agg_exprs.append(select_item)

        agg_from_sql = self._replace_identifiers(first.agg_from_sql, rename_map)
        agg_where_sql = self._replace_identifiers(first.agg_where_sql, rename_map)
        agg_sql_parts = [
            'SELECT',
            '    ' + ',\n    '.join(group_key_selects + agg_exprs),
            agg_from_sql,
        ]
        if agg_where_sql:
            agg_sql_parts.append(agg_where_sql)
        agg_sql_parts.append('GROUP BY ' + ', '.join(first.agg_group_items))
        agg_step = ExecutionStep(agg_name, '\n'.join(agg_sql_parts), 'reusable_aggregate')

        feature_steps: dict[str, ExecutionStep] = {}
        for item in group:
            feature_from_sql = self._replace_relation_references(item.final_from_sql, {item.agg_cte_name: agg_name})
            feature_sql = '\n'.join([
                'SELECT',
                '    ' + ',\n    '.join(item.entity_select_items + [item.feature_select_item]),
                feature_from_sql,
            ])
            feature_steps[item.feature_name] = ExecutionStep(f'feature_{item.feature_name}', feature_sql, 'feature_projection')
        return reusable_steps, agg_step, feature_steps

    def _choose_richest_cte_body(self, bodies: list[str]) -> str:
        # Prefer the body with the richest output contract.  This covers common
        # feature families where one downstream feature needs extra passthrough
        # columns, while the other features use a strict subset.
        def score(body: str) -> tuple[int, int]:
            ctes, final_sql = self._extract_ctes_and_final(body) if body.lstrip().upper().startswith('WITH') else ([], body)
            select_items, _, _, _ = self._split_select_from_where_group(final_sql)
            return (len(select_items), len(body))

        return max(bodies, key=score)

    def _try_parse_cte_chain_feature_step(self, feature_name: str, step: ExecutionStep, entity_key_count: int) -> _ParsedCteChainFeatureStep | None:
        sql = step.sql.strip()
        if not sql.upper().startswith('WITH'):
            return None
        ctes, final_sql = self._extract_ctes_and_final(sql)
        if len(ctes) < 3:
            return None
        agg_name, agg_body = ctes[-1]
        agg_select_items, agg_from_sql, agg_where_sql, agg_group_sql = self._split_select_from_where_group(agg_body)
        if not agg_select_items or not agg_from_sql or not agg_group_sql:
            return None
        entity_items, feature_item, final_from_sql = self._split_final_select(final_sql, entity_key_count)
        if len(entity_items) != entity_key_count or not feature_item or not final_from_sql:
            return None
        agg_group_items = self._split_top_level_csv(agg_group_sql.removeprefix('GROUP BY ').strip())
        if not agg_group_items:
            return None
        return _ParsedCteChainFeatureStep(
            feature_name=feature_name,
            original_step_name=step.step_name,
            ctes=ctes,
            entity_select_items=entity_items,
            feature_select_item=feature_item,
            final_from_sql=final_from_sql,
            agg_select_items=agg_select_items,
            agg_from_sql=agg_from_sql,
            agg_where_sql=agg_where_sql,
            agg_group_items=agg_group_items,
        )

    def _build_group_steps(self, group: list[_ParsedFeatureStep]):
        first = group[0]
        base_name = self._step_name('base_reuse', [item.feature_name for item in group], first.cte1_body)
        agg_name = self._step_name('agg_reuse', [item.feature_name for item in group], first.cte2_body)

        cte1_items = self._merge_select_items([item.cte1_select_items for item in group])
        base_sql_parts = ['SELECT', '    ' + ',\n    '.join(cte1_items)]
        if first.cte1_from_sql:
            base_sql_parts.append(first.cte1_from_sql)
        if first.cte1_where_sql:
            base_sql_parts.append(first.cte1_where_sql)
        base_step = ExecutionStep(base_name, '\n'.join(base_sql_parts), 'reusable_base')

        group_key_selects: list[str] = []
        for item in first.cte2_select_items:
            item_no_alias = self._strip_alias(item)
            if item in first.cte2_group_items or item_no_alias in first.cte2_group_items:
                group_key_selects.append(item)
        agg_exprs: list[str] = []
        for item in group:
            for select_item in item.cte2_select_items:
                item_no_alias = self._strip_alias(select_item)
                if select_item in group_key_selects or item_no_alias in first.cte2_group_items:
                    continue
                if select_item not in agg_exprs:
                    agg_exprs.append(select_item)
        agg_sql = '\n'.join([
            'SELECT',
            '    ' + ',\n    '.join(group_key_selects + agg_exprs),
            f'FROM {base_name}',
            'GROUP BY ' + ', '.join(first.cte2_group_items),
        ])
        agg_step = ExecutionStep(agg_name, agg_sql, 'reusable_aggregate')

        feature_steps: dict[str, ExecutionStep] = {}
        for item in group:
            feature_sql = '\n'.join([
                'SELECT',
                '    ' + ',\n    '.join(item.entity_select_items + [item.feature_select_item]),
                self._replace_relation_references(item.final_from_sql, {item.cte2_name: agg_name}),
            ])
            feature_steps[item.feature_name] = ExecutionStep(f'feature_{item.feature_name}', feature_sql, 'feature_projection')
        return base_step, agg_step, feature_steps

    def _try_parse_feature_step(self, feature_name: str, step: ExecutionStep, entity_key_count: int) -> _ParsedFeatureStep | None:
        sql = step.sql.strip()
        if not sql.upper().startswith('WITH'):
            return None
        ctes, final_sql = self._extract_ctes_and_final(sql)
        if len(ctes) != 2:
            return None
        (cte1_name, cte1_body), (cte2_name, cte2_body) = ctes
        cte1_select_items, cte1_from_sql, cte1_where_sql, _ = self._split_select_from_where_group(cte1_body)
        cte2_select_items, cte2_from_sql, _, cte2_group_sql = self._split_select_from_where_group(cte2_body)
        if not cte1_select_items or not cte2_select_items or not cte2_group_sql:
            return None
        entity_items, feature_item, final_from_sql = self._split_final_select(final_sql, entity_key_count)
        if len(entity_items) != entity_key_count or not feature_item or not final_from_sql:
            return None
        return _ParsedFeatureStep(
            feature_name=feature_name,
            original_step_name=step.step_name,
            cte1_name=cte1_name,
            cte1_body=cte1_body,
            cte2_name=cte2_name,
            cte2_body=cte2_body,
            entity_select_items=entity_items,
            feature_select_item=feature_item,
            final_from_sql=final_from_sql,
            cte1_select_items=cte1_select_items,
            cte1_from_sql=cte1_from_sql,
            cte1_where_sql=cte1_where_sql,
            cte2_select_items=cte2_select_items,
            cte2_from_name=self._extract_from_name(cte2_from_sql),
            cte2_group_items=self._split_top_level_csv(cte2_group_sql.removeprefix('GROUP BY ').strip()),
        )

    def _extract_ctes_and_final(self, sql: str):
        idx = 5
        n = len(sql)
        ctes = []
        while idx < n:
            while idx < n and sql[idx].isspace():
                idx += 1
            name_start = idx
            while idx < n and not sql.startswith(' AS (', idx):
                idx += 1
            if idx >= n:
                break
            name = sql[name_start:idx].strip()
            idx += 5
            depth = 1
            body_start = idx
            while idx < n and depth > 0:
                ch = sql[idx]
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                idx += 1
            body = sql[body_start:idx-1].strip()
            ctes.append((name, body))
            while idx < n and sql[idx].isspace():
                idx += 1
            if idx < n and sql[idx] == ',':
                idx += 1
                continue
            break
        return ctes, sql[idx:].strip()

    def _split_select_from_where_group(self, sql: str):
        rest = self._strip_leading_keyword(sql, 'SELECT')
        if rest is None:
            return [], '', '', ''
        from_pos = self._find_top_level_keyword(rest, ' FROM ')
        if from_pos < 0:
            return [], '', '', ''
        select_sql = rest[:from_pos].strip()
        tail = rest[from_pos + 1:].strip()
        where_pos = self._find_top_level_keyword(tail, ' WHERE ')
        group_pos = self._find_top_level_keyword(tail, ' GROUP BY ')
        if where_pos >= 0 and (group_pos < 0 or where_pos < group_pos):
            from_sql = tail[:where_pos].strip()
            if group_pos >= 0:
                where_sql = tail[where_pos + 1:group_pos].strip()
                group_sql = tail[group_pos + 1:].strip()
            else:
                where_sql = tail[where_pos + 1:].strip()
                group_sql = ''
        elif group_pos >= 0:
            from_sql = tail[:group_pos].strip()
            where_sql = ''
            group_sql = tail[group_pos + 1:].strip()
        else:
            from_sql = tail.strip()
            where_sql = ''
            group_sql = ''
        return self._split_top_level_csv(select_sql), from_sql, where_sql, group_sql

    def _split_final_select(self, sql: str, entity_key_count: int):
        rest = self._strip_leading_keyword(sql, 'SELECT')
        if rest is None:
            return [], '', ''
        from_pos = self._find_top_level_keyword(rest, ' FROM ')
        if from_pos < 0:
            return [], '', ''
        select_items = self._split_top_level_csv(rest[:from_pos].strip())
        if len(select_items) < entity_key_count + 1:
            return [], '', ''
        from_sql = rest[from_pos + 1:].strip()
        return select_items[:entity_key_count], select_items[entity_key_count], from_sql

    def _extract_from_name(self, from_sql: str) -> str:
        body = from_sql.removeprefix('FROM ').strip()
        return body.split()[0] if body else ''

    def _strip_leading_keyword(self, sql: str, keyword: str) -> str | None:
        stripped = sql.lstrip()
        if not stripped.upper().startswith(keyword.upper()):
            return None
        rest = stripped[len(keyword):]
        if rest and not rest[0].isspace():
            return None
        return rest.lstrip()

    def _find_top_level_keyword(self, sql: str, keyword: str) -> int:
        depth = 0
        upper = sql.upper()
        target = ' '.join(keyword.upper().split())
        i = 0
        while i <= len(sql) - len(target):
            ch = sql[i]
            if ch == '(':
                depth += 1
                i += 1
                continue
            if ch == ')':
                depth -= 1
                i += 1
                continue
            if depth == 0 and upper.startswith(target, i):
                before_ok = i == 0 or sql[i - 1].isspace()
                after_idx = i + len(target)
                after_ok = after_idx >= len(sql) or sql[after_idx].isspace()
                if before_ok and after_ok:
                    return i - 1 if i > 0 and sql[i - 1].isspace() else i
            i += 1
        return -1

    def _split_top_level_csv(self, sql: str) -> list[str]:
        items: list[str] = []
        depth = 0
        start = 0
        for i, ch in enumerate(sql):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ',' and depth == 0:
                items.append(sql[start:i].strip())
                start = i + 1
        tail = sql[start:].strip()
        if tail:
            items.append(tail)
        return items

    def _strip_alias(self, item: str) -> str:
        upper = item.upper()
        idx = upper.rfind(' AS ')
        return item[:idx].strip() if idx >= 0 else item.strip()

    def _merge_select_items(self, groups: list[list[str]]) -> list[str]:
        merged: OrderedDict[str, str] = OrderedDict()
        for items in groups:
            for item in items:
                key = self._strip_alias(item)
                merged.setdefault(key, item)
        return list(merged.values())

    def _normalize_from_source(self, from_sql: str, cte_names: tuple[str, ...]) -> str:
        normalized = from_sql
        for name in cte_names:
            normalized = self._replace_identifiers(normalized, {name: '__CTE__'})
        return normalized


    def _replace_relation_references(self, sql: str, replacements: dict[str, str]) -> str:
        rewritten = sql
        for old, new in sorted(replacements.items(), key=lambda kv: len(kv[0]), reverse=True):
            # Replace relation occurrences in FROM/JOIN while preserving the old
            # alias.  If no alias was present, add the original name as an alias
            # so existing qualified references such as ``agg.feature`` remain
            # valid after the relation itself is renamed.
            pattern = re.compile(
                rf'\b(?P<kw>FROM|JOIN)\s+{re.escape(old)}'
                rf'(?P<alias>\s+AS\s+[A-Za-z_][A-Za-z0-9_]*|\s+[A-Za-z_][A-Za-z0-9_]*)?',
                flags=re.IGNORECASE,
            )

            def repl(match: re.Match) -> str:
                alias = match.group('alias') or f' AS {old}'
                return f"{match.group('kw')} {new}{alias}"

            rewritten = pattern.sub(repl, rewritten)
        return rewritten

    def _replace_identifiers(self, sql: str, replacements: dict[str, str]) -> str:
        rewritten = sql
        for old, new in sorted(replacements.items(), key=lambda kv: len(kv[0]), reverse=True):
            pattern = re.compile(rf'(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])')
            rewritten = pattern.sub(new, rewritten)
        return rewritten

    def _safe_identifier(self, name: str) -> str:
        cleaned = re.sub(r'[^A-Za-z0-9_]+', '_', name).strip('_') or 'cte'
        if cleaned[0].isdigit():
            cleaned = 'cte_' + cleaned
        return cleaned.lower()

    def _step_name(self, prefix: str, feature_names: list[str], seed_sql: str) -> str:
        digest = md5((repr(sorted(feature_names)) + seed_sql).encode('utf-8')).hexdigest()[:10]
        return f'{prefix}_{digest}'
