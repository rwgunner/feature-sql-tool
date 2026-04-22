from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


FEATURE = FeatureSpec(
    feature_name="avg_paid_amount_recent_30d",
    sql_file_path=Path(__file__).resolve().parents[1] / "sql_samples" / "feature_avg_paid_amount_recent_30d.sql",
    entity_key="client_id",
    dialect="spark",
)


def test_complex_cte_lineage_resolves_value_and_filter_paths() -> None:
    tool = FeatureSqlTool()
    result = tool.analyze_features([FEATURE])[0]

    assert result.unresolved_columns == []
    assert "src:dm_payments.amount" in result.source_columns
    assert "src:dm_payments.payment_id" in result.source_columns
    assert "src:dm_payments.payment_dt" in result.source_columns
    assert "src:dm_payments.payment_status" in result.source_columns

    assert any(item.endswith(':is_paid_recent_flag') for item in result.intermediate_features)
    assert any(item.endswith(':paid_amount') for item in result.intermediate_features)

    assert any(item.endswith(':is_paid_recent_flag') for item in result.filter_only_intermediate_features)
    assert not any(item.endswith(':paid_amount') for item in result.filter_only_intermediate_features)
