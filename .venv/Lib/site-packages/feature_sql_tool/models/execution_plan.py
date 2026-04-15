from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ExecutionStep:
    step_name: str
    sql: str
    step_type: str  # entity / reusable_base / reusable_aggregate / feature / final_select


@dataclass
class ExecutionPlan:
    entity_step: Optional[ExecutionStep] = None
    base_steps: List[ExecutionStep] = field(default_factory=list)
    reusable_steps: List[ExecutionStep] = field(default_factory=list)
    aggregate_steps: List[ExecutionStep] = field(default_factory=list)
    feature_steps: Dict[str, List[ExecutionStep]] = field(default_factory=dict)
    final_step: Optional[ExecutionStep] = None
    feature_to_step_name: Dict[str, str] = field(default_factory=dict)
    feature_to_column_name: Dict[str, str] = field(default_factory=dict)
