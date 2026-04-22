from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


FEATURE = FeatureSpec(
    feature_name="payment_risk_score",
    sql_file_path=Path(__file__).resolve().parents[1] / "sql_samples" / "feature_payment_risk_score.sql",
    entity_keys=["client_id", "payment_id"],
    dialect="spark",
)


def test_union_value_lineage_is_symmetric_across_branches() -> None:
    tool = FeatureSqlTool()
    result = tool.analyze_features([FEATURE])[0]

    assert 'src:dm_payments_current.amount' in result.value_source_columns
    assert 'src:dm_payments_archive.amount' in result.value_source_columns
    assert 'src:dm_payments_current.channel' in result.value_source_columns
    assert 'src:dm_payments_archive.channel' in result.value_source_columns
    assert 'src:dm_payments_current.payment_status' in result.value_source_columns
    assert 'src:dm_payments_archive.payment_status' in result.value_source_columns

    assert 'src:dm_payments_current.amount' in result.source_columns
    assert 'src:dm_payments_archive.amount' in result.source_columns
    assert 'src:dm_payments_current.channel' in result.source_columns
    assert 'src:dm_payments_archive.channel' in result.source_columns
    assert 'src:dm_payments_current.payment_status' in result.source_columns
    assert 'src:dm_payments_archive.payment_status' in result.source_columns
    assert result.unresolved_columns == []
