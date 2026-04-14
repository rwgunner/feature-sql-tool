from __future__ import annotations

from typing import Optional

from sqlglot import exp


class ColumnResolver:
    """
    Draft column resolver.

    MVP behavior:
    - if a column has a table qualifier -> treat it as a source table reference
    - if it has no qualifier -> keep it unresolved for now
    """

    def resolve_column(self, column: exp.Column) -> dict[str, Optional[str]]:
        table_name = column.table or None
        column_name = column.name or None

        return {
            "table_name": table_name,
            "column_name": column_name,
            "resolved_as": "source_column" if column_name else "unknown",
        }
