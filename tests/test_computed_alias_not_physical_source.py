from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_computed_cte_alias_is_not_reported_as_physical_source(tmp_path: Path) -> None:
    sql_file = tmp_path / "feature_x.sql"
    sql_file.write_text(
        """
WITH base AS (
    SELECT
        id,
        amount * 2 AS current_amt_rur
    FROM raw_table
), agg AS (
    SELECT
        id,
        SUM(current_amt_rur) AS feature_x
    FROM base
    GROUP BY id
)
SELECT
    id,
    feature_x
FROM agg
""",
        encoding="utf-8",
    )

    result = FeatureSqlTool().analyze_features([
        FeatureSpec(
            feature_name="feature_x",
            sql_file_path=sql_file,
            entity_key="id",
            dialect="spark",
        )
    ])[0]

    assert "src:raw_table.amount" in result.source_columns
    assert "src:raw_table.id" in result.source_columns
    assert "src:raw_table.current_amt_rur" not in result.source_columns
    assert "src:raw_table.feature_x" not in result.source_columns
    assert "int:feature_x__scope_1:current_amt_rur" in result.intermediate_features
    assert "int:feature_x__scope_2:feature_x" in result.intermediate_features
    assert result.unresolved_columns == []
