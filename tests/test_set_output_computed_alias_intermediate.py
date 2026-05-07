from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_computed_set_output_aliases_are_intermediate_not_sources(tmp_path: Path):
    sql = """
    WITH unioned AS (
        SELECT
            id,
            CONCAT(CAST(agreement_rk AS STRING), '_', '2') AS unique_agreement_rk,
            2 AS is_term_deposit,
            amount
        FROM raw_deposit
        UNION ALL
        SELECT
            id,
            CONCAT(CAST(agreement_rk AS STRING), '_', '1') AS unique_agreement_rk,
            CASE WHEN amount > 0 THEN 1 ELSE 4 END AS is_term_deposit,
            amount
        FROM raw_deposit
    ), agg AS (
        SELECT
            id,
            COUNT(CASE WHEN is_term_deposit = 1 THEN unique_agreement_rk END) AS dep_cnt
        FROM unioned
        GROUP BY id
    )
    SELECT
        id,
        dep_cnt
    FROM agg
    """
    sql_path = tmp_path / "feature_dep_cnt.sql"
    sql_path.write_text(sql)

    result = FeatureSqlTool().analyze_features([
        FeatureSpec(
            feature_name="dep_cnt",
            sql_file_path=sql_path,
            entity_key="id",
            dialect="spark",
        )
    ])[0]

    assert any(item.endswith(":unique_agreement_rk") for item in result.intermediate_features)
    assert any(item.endswith(":is_term_deposit") for item in result.intermediate_features)
    assert "src:raw_deposit.unique_agreement_rk" not in result.source_columns
    assert "src:raw_deposit.is_term_deposit" not in result.source_columns
    assert "src:raw_deposit.agreement_rk" in result.source_columns
    assert "src:raw_deposit.amount" in result.source_columns
    assert result.unresolved_columns == []
