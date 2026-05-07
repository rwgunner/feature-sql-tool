from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_optimized_unified_sql_reuses_deep_cte_chain_with_composite_keys(tmp_path: Path) -> None:
    cnt_sql = """
WITH unioned AS (
    SELECT k1, k2, k3, agreement_rk, amount, open_dt, close_dt, 1 AS source_priority FROM src_a
    UNION ALL
    SELECT k1, k2, k3, agreement_rk, amount, open_dt, close_dt, 2 AS source_priority FROM src_b
), prepared AS (
    SELECT
        k1,
        k2,
        k3,
        agreement_rk,
        amount,
        CASE WHEN open_dt <= k3 AND k3 < close_dt THEN 1 ELSE 0 END AS is_active
    FROM unioned
), ranked AS (
    SELECT
        k1,
        k2,
        k3,
        agreement_rk,
        amount,
        is_active,
        ROW_NUMBER() OVER (PARTITION BY agreement_rk, k3 ORDER BY amount DESC) AS rn
    FROM prepared
), agg AS (
    SELECT
        k1,
        k2,
        k3,
        COUNT(CASE WHEN is_active = 1 AND rn = 1 AND amount > 1000 THEN 1 END) AS cnt_dep_act
    FROM ranked
    GROUP BY k1, k2, k3
)
SELECT
    keys.k1,
    keys.k2,
    keys.k3,
    CAST(agg.cnt_dep_act AS INT) AS cnt_dep_act
FROM keys AS keys
LEFT JOIN agg AS agg ON agg.k1 = keys.k1 AND agg.k2 = keys.k2 AND agg.k3 = keys.k3
"""
    sum_sql = """
WITH unioned AS (
    SELECT k1, k2, k3, agreement_rk, amount, 1 AS source_priority FROM src_a
    UNION ALL
    SELECT k1, k2, k3, agreement_rk, amount, 2 AS source_priority FROM src_b
), prepared AS (
    SELECT
        k1,
        k2,
        k3,
        agreement_rk,
        amount
    FROM unioned
), ranked AS (
    SELECT
        k1,
        k2,
        k3,
        agreement_rk,
        amount,
        ROW_NUMBER() OVER (PARTITION BY agreement_rk, k3 ORDER BY amount DESC) AS rn
    FROM prepared
), agg AS (
    SELECT
        k1,
        k2,
        k3,
        SUM(CASE WHEN rn = 1 THEN amount ELSE 0 END) AS sum_dep_now
    FROM ranked
    GROUP BY k1, k2, k3
)
SELECT
    keys.k1,
    keys.k2,
    keys.k3,
    CAST(agg.sum_dep_now AS INT) AS sum_dep_now
FROM keys AS keys
LEFT JOIN agg AS agg ON agg.k1 = keys.k1 AND agg.k2 = keys.k2 AND agg.k3 = keys.k3
"""
    cnt_path = tmp_path / "cnt.sql"
    sum_path = tmp_path / "sum.sql"
    cnt_path.write_text(cnt_sql, encoding="utf-8")
    sum_path.write_text(sum_sql, encoding="utf-8")

    features = [
        FeatureSpec("cnt_dep_act", cnt_path, entity_keys=["k1", "k2", "k3"], dialect="spark"),
        FeatureSpec("sum_dep_now", sum_path, entity_keys=["k1", "k2", "k3"], dialect="spark"),
    ]

    sql = FeatureSqlTool().build_optimized_unified_sql(features, strict_mode=True, fallback_to_legacy=False)

    assert "reuse_unioned_" in sql
    assert "reuse_prepared_" in sql
    assert "reuse_ranked_" in sql
    assert "agg_reuse_" in sql
    assert "feature_cnt_dep_act" in sql
    assert "feature_sum_dep_now" in sql
    assert "COUNT(CASE WHEN is_active = 1 AND rn = 1 AND amount > 1000 THEN 1 END) AS cnt_dep_act" in sql
    assert "SUM(CASE WHEN rn = 1 THEN amount ELSE 0 END) AS sum_dep_now" in sql
    assert "LEFT JOIN agg_reuse_" in sql
    assert sql.count("WITH unioned AS") == 0
    assert "CAST(agg.cnt_dep_act AS INT) AS cnt_dep_act" in sql
    assert "CAST(agg.sum_dep_now AS INT) AS sum_dep_now" in sql
