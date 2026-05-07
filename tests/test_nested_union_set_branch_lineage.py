from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_lineage_does_not_crash_on_three_branch_union_with_computed_outputs(tmp_path: Path):
    sql = """
WITH u AS (
    SELECT id, a + 1 AS x FROM t1
    UNION ALL
    SELECT id, b + 2 AS x FROM t2
    UNION ALL
    SELECT id, c + 3 AS x FROM t3
), agg AS (
    SELECT id, SUM(x) AS nested_union_feature
    FROM u
    GROUP BY id
)
SELECT
    keys.id,
    agg.nested_union_feature AS nested_union_feature
FROM keys AS keys
LEFT JOIN agg AS agg
    ON agg.id = keys.id
"""
    sql_path = tmp_path / "feature_nested_union.sql"
    sql_path.write_text(sql, encoding="utf-8")

    result = FeatureSqlTool().analyze_features([
        FeatureSpec(
            feature_name="nested_union_feature",
            sql_file_path=sql_path,
            entity_key="id",
            dialect="spark",
        )
    ])[0]

    assert "src:keys.id" in result.source_columns
    assert any(source.startswith("src:t1.") for source in result.source_columns)
    assert any(source.startswith("src:t2.") for source in result.source_columns)
    assert any(source.startswith("src:t3.") for source in result.source_columns)
