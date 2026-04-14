from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class FeatureSpec:
    """
    Description of a single SQL feature.

    sql_file_path: path to a .sql file with feature logic.
    final_alias: alias expected in the final SELECT of that file.
    entity_key: entity key, for example client_id.
    """

    feature_name: str
    sql_file_path: Path
    final_alias: str
    entity_key: str
    dialect: str = "spark"
    grain: Optional[str] = None
    snapshot_column: Optional[str] = None

    def validate(self) -> None:
        if self.sql_file_path.suffix.lower() != ".sql":
            raise ValueError(
                f"Feature '{self.feature_name}': expected .sql file, got '{self.sql_file_path}'."
            )
        if not self.sql_file_path.exists():
            raise FileNotFoundError(
                f"Feature '{self.feature_name}': SQL file not found: {self.sql_file_path}"
            )
        if not self.sql_file_path.is_file():
            raise ValueError(
                f"Feature '{self.feature_name}': path is not a file: {self.sql_file_path}"
            )
