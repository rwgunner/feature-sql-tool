from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityKeySpec:
    keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.keys:
            raise ValueError("EntityKeySpec requires at least one key")
        normalized = tuple(str(key).strip() for key in self.keys if str(key).strip())
        if not normalized:
            raise ValueError("EntityKeySpec requires at least one non-empty key")
        object.__setattr__(self, 'keys', normalized)

    @property
    def primary_key(self) -> str:
        return self.keys[0]

    def as_list(self) -> list[str]:
        return list(self.keys)
