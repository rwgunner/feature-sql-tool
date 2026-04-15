from __future__ import annotations

from pathlib import Path


class SqlFileLoader:
    def load(self, file_path: Path) -> str:
        content = file_path.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError(f"SQL file is empty: {file_path}")
        return content
