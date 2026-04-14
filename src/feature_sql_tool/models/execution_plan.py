from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ExecutionStep:
    step_name: str
    sql: str
    step_type: str  # base_cte / reusable_cte / feature_cte / final_select


@dataclass
class ExecutionPlan:
    base_steps: List[ExecutionStep] = field(default_factory=list)
    reusable_steps: List[ExecutionStep] = field(default_factory=list)
    feature_steps: Dict[str, List[ExecutionStep]] = field(default_factory=dict)
    final_steps: List[ExecutionStep] = field(default_factory=list)
