from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .feature_spec import FeatureSpec


@dataclass(frozen=True)
class VectorBuildRequest:
    features: list[FeatureSpec]
    entity_key: str
    entity_sql_file_path: Optional[Path] = None
    dialect: str = "spark"
