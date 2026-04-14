# feature-sql-tool

`feature-sql-tool` is a draft Python package for two related tasks:

1. analyzing SQL scripts for model features and extracting dependency lineage;
2. building a unified SQL query for a model input vector from multiple feature SQL files.

The package is designed around `sqlglot` and uses a `src` layout with modern `pyproject.toml` packaging, which is the recommended approach in the Python Packaging User Guide. The packaging guide recommends defining build metadata in `pyproject.toml`, and the tool recommendations guide recommends building distributions with `python -m build` rather than calling `setup.py` directly. citeturn721430search0turn721430search2turn721430search6turn721430search7turn721430search9

## Features in this first version

- `FeatureSpec` points to a `.sql` file instead of storing long SQL inline.
- SQL loading, parsing, scope registration, lineage extraction, graph classification, and unified SQL generation are split into separate modules.
- A first MVP service API is included.

## Install locally

```bash
python -m pip install -U pip
pip install -e .
```

For development extras:

```bash
pip install -e .[dev]
```

## Build distributions

```bash
python -m pip install -U build
python -m build
```

This creates:

- `dist/*.tar.gz` — source distribution
- `dist/*.whl` — wheel

## Check distributions

```bash
python -m pip install -U twine
twine check dist/*
```

## Upload to PyPI

```bash
python -m pip install -U twine
twine upload dist/*
```

## Install from a downloaded archive

After publishing to PyPI:

```bash
pip download feature-sql-tool
pip install feature_sql_tool-0.1.0-py3-none-any.whl
```

## Minimal usage example

```python
from pathlib import Path

from feature_sql_tool import FeatureSqlTool, FeatureSpec

features = [
    FeatureSpec(
        feature_name="avg_payment_30d",
        sql_file_path=Path("sql/avg_payment_30d.sql"),
        final_alias="avg_payment_30d",
        entity_key="client_id",
        dialect="spark",
    ),
]

tool = FeatureSqlTool()
results = tool.analyze_features(features)
print(results[0].source_columns)
```

## Notes

This package is still an MVP scaffold. Deep recursive CTE resolution, UNION-aware lineage, and real common-subgraph optimization are not fully implemented yet.
