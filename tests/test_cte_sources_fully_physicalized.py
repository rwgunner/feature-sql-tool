from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


FEATURE = FeatureSpec(
    feature_name="client_payment_risk_score_30d",
    sql_file_path=Path(__file__).resolve().parents[1] / "sql_samples" / "feature_client_payment_risk_score_30d.sql",
    entity_key="client_id",
    dialect="spark",
)


def test_cte_level_sources_are_fully_physicalized() -> None:
    result = FeatureSqlTool().analyze_features([FEATURE])[0]

    assert result.unresolved_columns == []
    assert not any(item.startswith('src:payment_base.') for item in result.source_columns)
    assert 'src:dm_payments.channel' in result.source_columns
    assert 'src:dm_payments.client_id' in result.source_columns
    assert 'src:dm_payments.payment_dt' in result.source_columns
    assert 'src:dm_clients.segment' in result.source_columns
    assert 'src:dm_chargebacks.chargeback_dt' in result.source_columns
