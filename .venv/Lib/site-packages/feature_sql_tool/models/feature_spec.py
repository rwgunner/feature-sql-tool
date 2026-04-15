from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class FeatureSpec:
    feature_name: str
    sql_file_path: Path
    final_alias: str
    entity_key: str
    dialect: str = "spark"
    grain: Optional[str] = None
    snapshot_column: Optional[str] = None

    def validate(self) -> None:
        if self.sql_file_path.suffix.lower() != ".sql":
            raise ValueError(f"Expected .sql file for feature '{self.feature_name}', got {self.sql_file_path}")
        if not self.sql_file_path.exists() or not self.sql_file_path.is_file():
            raise FileNotFoundError(f"SQL file not found for feature '{self.feature_name}': {self.sql_file_path}")
