from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_window_expression_over_union_all_has_clean_lineage(tmp_path: Path):
    sql_path = tmp_path / "feature_latest_amount.sql"
    sql_path.write_text(
        """
WITH unioned AS (
    SELECT id, agreement_rk, amount, 1 AS priority FROM first_source
    UNION ALL
    SELECT id, agreement_rk, amount, 2 AS priority FROM second_source
    UNION ALL
    SELECT id, agreement_rk, amount, 3 AS priority FROM third_source
), ranked AS (
    SELECT
        id,
        amount,
        ROW_NUMBER() OVER (
            PARTITION BY agreement_rk
            ORDER BY priority ASC
        ) AS rn
    FROM unioned
), aggregated AS (
    SELECT
        id,
        SUM(amount) AS latest_amount
    FROM ranked
    WHERE rn = 1
    GROUP BY id
)
SELECT
    keys.id AS id,
    CAST(aggregated.latest_amount AS INT) AS latest_amount
FROM keys AS keys
LEFT JOIN aggregated AS aggregated
    ON aggregated.id = keys.id
""".strip(),
        encoding="utf-8",
    )

    result = FeatureSqlTool().analyze_features([
        FeatureSpec(
            feature_name="latest_amount",
            sql_file_path=sql_path,
            entity_key="id",
            dialect="spark",
        )
    ])[0]

    assert not any("__set_branch__" in item for item in result.intermediate_features)
    assert not any("__set_branch__" in item for item in result.filter_only_intermediate_features)
    assert "unresolved:__unresolved__.agreement_rk" not in result.unresolved_columns
    assert result.unresolved_columns == []
    assert "src:first_source.agreement_rk" in result.source_columns
    assert "src:second_source.agreement_rk" in result.source_columns
    assert "src:third_source.agreement_rk" in result.source_columns
    assert any(item.endswith(":rn") for item in result.filter_only_intermediate_features)
