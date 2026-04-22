from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .entity_key import EntityKeySpec


@dataclass(frozen=True)
class FeatureSpec:
    feature_name: str
    sql_file_path: Path
    entity_key: str | None = None
    dialect: str = "spark"
    snapshot_column: Optional[str] = None
    entity_keys: tuple[str, ...] | list[str] | None = None

    def __post_init__(self) -> None:
        keys = self.entity_keys
        if keys is None:
            if self.entity_key is None:
                raise ValueError(f"Feature '{self.feature_name}' requires entity_key or entity_keys")
            keys = (self.entity_key,)
        elif isinstance(keys, str):
            keys = (keys,)
        else:
            keys = tuple(keys)

        key_spec = EntityKeySpec(tuple(keys))
        object.__setattr__(self, 'entity_keys', key_spec.keys)
        if self.entity_key is None:
            object.__setattr__(self, 'entity_key', key_spec.primary_key)

    @property
    def entity_key_spec(self) -> EntityKeySpec:
        return EntityKeySpec(tuple(self.entity_keys or ()))

    @property
    def final_alias(self) -> str:
        return self.feature_name

    @property
    def grain(self) -> str:
        return ','.join(self.entity_keys or ())

    def validate(self) -> None:
        if self.sql_file_path.suffix.lower() != ".sql":
            raise ValueError(f"Expected .sql file for feature '{self.feature_name}', got {self.sql_file_path}")
        if not self.sql_file_path.exists() or not self.sql_file_path.is_file():
            raise FileNotFoundError(f"SQL file not found for feature '{self.feature_name}': {self.sql_file_path}")
