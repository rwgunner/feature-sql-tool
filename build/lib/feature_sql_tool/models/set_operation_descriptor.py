from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SetOperationDescriptor:
    scope_name: str
    operation_type: str
    left_scope_name: str | None
    right_scope_name: str | None
    output_columns: tuple[str, ...]
    left_output_expressions: tuple[Any, ...] = ()
    right_output_expressions: tuple[Any, ...] = ()
