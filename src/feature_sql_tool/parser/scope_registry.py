from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScopeInfo:
    scope_name: str
    scope_obj: Any
    expression: Any
    parent_scope_name: Optional[str] = None
    source_names: List[str] = field(default_factory=list)


@dataclass
class ScopeRegistry:
    root_scope_name: Optional[str] = None
    scopes: Dict[str, ScopeInfo] = field(default_factory=dict)

    def add_scope(self, scope_info: ScopeInfo) -> None:
        self.scopes[scope_info.scope_name] = scope_info
        if self.root_scope_name is None:
            self.root_scope_name = scope_info.scope_name

    def get(self, scope_name: str) -> ScopeInfo:
        return self.scopes[scope_name]

    def all_scopes(self) -> List[ScopeInfo]:
        return list(self.scopes.values())
