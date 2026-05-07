from __future__ import annotations

import re

from feature_sql_tool.models.graph import DependencyNode

_NUMERIC_LITERAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_QUOTED_LITERAL_RE = re.compile(r"^(?:'[^']*'|\"[^\"]*\")$")


def _strip_literal_quotes(value: str) -> str:
    text = str(value or '').strip()
    if len(text) >= 2 and ((text[0] == text[-1] == "'") or (text[0] == text[-1] == '\"')):
        return text[1:-1]
    return text


def is_synthetic_intermediate_feature(node: DependencyNode) -> bool:
    """Return True for parser/set-operation artifacts that should not be user-facing.

    UNION/UNION ALL branch resolution can create helper intermediate nodes for
    anonymous positional outputs or literal branch expressions, for example:
    ``int:feature__scope_2:__pos_3`` or ``int:feature__scope_2:2``.  These nodes
    are useful while building the dependency graph but they are not meaningful
    feature lineage items, so public classifiers should hide them.

    Named literal aliases such as ``priority`` are intentionally kept: they often
    explain filter/window semantics and are useful in reports.
    """
    if node.node_type != 'intermediate_feature':
        return False

    if node.scope_name == '__set_branch__':
        return True

    name = str(node.name or '').strip()
    expression_sql = str(node.expression_sql or '').strip()

    if name.startswith('__pos_') or name.startswith('__col_') or name.startswith('__set_'):
        return True

    # Literal-only set branch artifacts commonly surface with the literal value
    # itself as the generated alias name, e.g. ``2`` for ``2 AS is_term_deposit``.
    # Keep semantic aliases like ``priority`` even when their expression is ``1``.
    if expression_sql:
        if name == expression_sql and (_NUMERIC_LITERAL_RE.match(name) or _QUOTED_LITERAL_RE.match(name)):
            return True
        # String literals may be normalized without quotes in the generated node
        # name, e.g. expression_sql="'FAILED_PAYMENT'" and name="FAILED_PAYMENT".
        # Hide these literal-only helper nodes while keeping semantic aliases such
        # as event_type, priority, is_term_deposit, etc.
        if _QUOTED_LITERAL_RE.match(expression_sql) and name == _strip_literal_quotes(expression_sql):
            return True

    return False
