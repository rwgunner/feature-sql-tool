from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .entity_key import EntityKeySpec
from .feature_spec import FeatureSpec


@dataclass(frozen=True)
class VectorBuildRequest:
    features: list[FeatureSpec]
    entity_key: str | None = None
    entity_sql_file_path: Optional[Path] = None
    dialect: str = "spark"
    entity_keys: tuple[str, ...] | list[str] | None = None

    def __post_init__(self) -> None:
        keys = self.entity_keys
        if keys is None:
            if self.entity_key is None:
                raise ValueError('VectorBuildRequest requires entity_key or entity_keys')
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
