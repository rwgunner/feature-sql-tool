from __future__ import annotations

from pathlib import Path

from feature_sql_tool.exceptions import SqlLoadError


class SqlFileLoader:
    """Loads SQL text from a file."""

    def load(self, file_path: Path) -> str:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - thin wrapper
            raise SqlLoadError(f"Failed to read SQL file '{file_path}': {exc}") from exc

        if not content.strip():
            raise SqlLoadError(f"SQL file '{file_path}' is empty.")

        return content
