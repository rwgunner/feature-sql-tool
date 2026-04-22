from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_payment_risk_score_value_source_columns_are_symmetric():
    base_dir = Path(__file__).resolve().parents[1]
    tool = FeatureSqlTool()
    spec = FeatureSpec(
        feature_name="payment_risk_score",
        sql_file_path=base_dir / "sql_samples" / "feature_payment_risk_score.sql",
        entity_keys=["client_id", "payment_id"],
        dialect="spark",
    )
    result = tool.analyze_features([spec])[0]

    expected_value_sources = {
        'src:dm_payments_current.amount',
        'src:dm_payments_archive.amount',
        'src:dm_payments_current.channel',
        'src:dm_payments_archive.channel',
        'src:dm_payments_current.payment_status',
        'src:dm_payments_archive.payment_status',
    }
    assert expected_value_sources.issubset(set(result.value_source_columns))
    assert result.unresolved_columns == []
