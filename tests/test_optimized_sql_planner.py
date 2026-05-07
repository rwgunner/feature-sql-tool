from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_build_optimized_unified_sql_merges_deposit_features():
    base_dir = Path(__file__).resolve().parents[1] / 'sql_samples'
    tool = FeatureSqlTool()
    features = [
        FeatureSpec(feature_name='cnt_dep_act', sql_file_path=base_dir / 'feature_cnt_dep_act.sql', entity_key='client_id', dialect='spark'),
        FeatureSpec(feature_name='sum_dep_now', sql_file_path=base_dir / 'feature_sum_dep_now.sql', entity_key='client_id', dialect='spark'),
    ]
    sql = tool.build_optimized_unified_sql(features)
    assert 'agg_' in sql
    assert 'cnt_dep_act' in sql
    assert 'sum_dep_now' in sql
    assert sql.count('FROM entity_base base') == 1


def _write_sql(path: Path, sql: str) -> Path:
    path.write_text(sql, encoding='utf-8')
    return path


def test_build_optimized_unified_sql_merges_two_key_features(tmp_path: Path):
    first_sql = """
WITH event_base AS (
    SELECT
        src.client_id,
        src.payment_id,
        src.event_dt,
        src.amount,
        src.status
    FROM payment_events AS src
    WHERE src.event_dt >= CAST('2026-03-01' AS DATE)
), event_agg AS (
    SELECT
        client_id,
        payment_id,
        SUM(amount) AS payment_amount_30d
    FROM event_base
    GROUP BY client_id, payment_id
)
SELECT
    keys.client_id AS client_id,
    keys.payment_id AS payment_id,
    CAST(ea.payment_amount_30d AS INT) AS payment_amount_30d
FROM payment_keys AS keys
LEFT JOIN event_agg AS ea
    ON ea.client_id = keys.client_id
   AND ea.payment_id = keys.payment_id
"""
    second_sql = """
WITH event_base AS (
    SELECT
        src.client_id,
        src.payment_id,
        src.event_dt,
        src.amount,
        src.status
    FROM payment_events AS src
    WHERE src.event_dt >= CAST('2026-03-01' AS DATE)
), event_agg AS (
    SELECT
        client_id,
        payment_id,
        COUNT(CASE WHEN status = 'FAILED' THEN 1 END) AS failed_event_cnt_30d
    FROM event_base
    GROUP BY client_id, payment_id
)
SELECT
    keys.client_id AS client_id,
    keys.payment_id AS payment_id,
    CAST(ea.failed_event_cnt_30d AS INT) AS failed_event_cnt_30d
FROM payment_keys AS keys
LEFT JOIN event_agg AS ea
    ON ea.client_id = keys.client_id
   AND ea.payment_id = keys.payment_id
"""
    features = [
        FeatureSpec(
            feature_name='payment_amount_30d',
            sql_file_path=_write_sql(tmp_path / 'feature_payment_amount_30d.sql', first_sql),
            entity_keys=['client_id', 'payment_id'],
            dialect='spark',
        ),
        FeatureSpec(
            feature_name='failed_event_cnt_30d',
            sql_file_path=_write_sql(tmp_path / 'feature_failed_event_cnt_30d.sql', second_sql),
            entity_keys=['client_id', 'payment_id'],
            dialect='spark',
        ),
    ]
    sql = FeatureSqlTool().build_optimized_unified_sql(features, fallback_to_legacy=False)

    assert 'SELECT DISTINCT client_id, payment_id FROM' in sql
    assert 'base.client_id = s1.client_id AND base.payment_id = s1.payment_id' in sql
    assert 'SUM(amount) AS payment_amount_30d' in sql
    assert "COUNT(CASE WHEN status = 'FAILED' THEN 1 END) AS failed_event_cnt_30d" in sql


def test_build_optimized_unified_sql_merges_three_key_features(tmp_path: Path):
    first_sql = """
WITH account_base AS (
    SELECT
        src.client_id,
        src.account_id,
        src.calc_report_dt,
        src.balance_amt,
        src.status
    FROM account_daily AS src
    WHERE src.calc_report_dt >= CAST('2026-03-01' AS DATE)
), account_agg AS (
    SELECT
        client_id,
        account_id,
        calc_report_dt,
        SUM(balance_amt) AS balance_sum
    FROM account_base
    GROUP BY client_id, account_id, calc_report_dt
)
SELECT
    keys.client_id AS client_id,
    keys.account_id AS account_id,
    keys.calc_report_dt AS calc_report_dt,
    CAST(aa.balance_sum AS INT) AS balance_sum
FROM account_keys AS keys
LEFT JOIN account_agg AS aa
    ON aa.client_id = keys.client_id
   AND aa.account_id = keys.account_id
   AND aa.calc_report_dt = keys.calc_report_dt
"""
    second_sql = """
WITH account_base AS (
    SELECT
        src.client_id,
        src.account_id,
        src.calc_report_dt,
        src.balance_amt,
        src.status
    FROM account_daily AS src
    WHERE src.calc_report_dt >= CAST('2026-03-01' AS DATE)
), account_agg AS (
    SELECT
        client_id,
        account_id,
        calc_report_dt,
        MAX(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_flag
    FROM account_base
    GROUP BY client_id, account_id, calc_report_dt
)
SELECT
    keys.client_id AS client_id,
    keys.account_id AS account_id,
    keys.calc_report_dt AS calc_report_dt,
    CAST(aa.active_flag AS INT) AS active_flag
FROM account_keys AS keys
LEFT JOIN account_agg AS aa
    ON aa.client_id = keys.client_id
   AND aa.account_id = keys.account_id
   AND aa.calc_report_dt = keys.calc_report_dt
"""
    features = [
        FeatureSpec(
            feature_name='balance_sum',
            sql_file_path=_write_sql(tmp_path / 'feature_balance_sum.sql', first_sql),
            entity_keys=['client_id', 'account_id', 'calc_report_dt'],
            dialect='spark',
        ),
        FeatureSpec(
            feature_name='active_flag',
            sql_file_path=_write_sql(tmp_path / 'feature_active_flag.sql', second_sql),
            entity_keys=['client_id', 'account_id', 'calc_report_dt'],
            dialect='spark',
        ),
    ]
    sql = FeatureSqlTool().build_optimized_unified_sql(features, fallback_to_legacy=False)

    assert 'SELECT DISTINCT client_id, account_id, calc_report_dt FROM' in sql
    assert 'base.client_id = s1.client_id AND base.account_id = s1.account_id AND base.calc_report_dt = s1.calc_report_dt' in sql
    assert 'SUM(balance_amt) AS balance_sum' in sql
    assert "MAX(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_flag" in sql
