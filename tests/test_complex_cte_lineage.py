from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


FEATURE = FeatureSpec(
    feature_name="avg_paid_amount_recent_30d",
    sql_file_path=Path(__file__).resolve().parents[1] / "sql_samples" / "feature_avg_paid_amount_recent_30d.sql",
    final_alias="avg_paid_amount_recent_30d",
    entity_key="client_id",
    dialect="spark",
    grain="client_id",
)


def test_complex_cte_lineage_resolves_physical_sources() -> None:
    tool = FeatureSqlTool()
    result = tool.analyze_features([FEATURE])[0]

    assert "src:dm_payments.client_id" in result.source_columns
    assert "src:dm_payments.payment_id" in result.source_columns
    assert "src:dm_payments.amount" in result.source_columns
    assert "src:dm_payments.payment_dt" in result.source_columns
    assert "src:dm_payments.payment_status" in result.source_columns
    assert all(not item.startswith("src:fp.") for item in result.source_columns)
    assert result.unresolved_columns == []


def test_complex_cte_lineage_computed_aliases() -> None:
    tool = FeatureSqlTool()
    result = tool.analyze_features([FEATURE])[0]

    assert any(item.endswith(":is_paid_recent_flag") for item in result.intermediate_features)
    assert any(item.endswith(":paid_amount") for item in result.intermediate_features)
    assert any(item.endswith(":is_paid_recent_flag") for item in result.filter_only_intermediate_features)
    assert all(not item.endswith(":paid_amount") for item in result.filter_only_intermediate_features)


def test_complex_cte_lineage_roles() -> None:
    tool = FeatureSqlTool()
    result = tool.analyze_features([FEATURE])[0]

    assert "src:dm_payments.amount" in result.value_source_columns
    assert "src:dm_payments.payment_id" in result.value_source_columns
    assert "src:dm_payments.payment_dt" in result.filter_source_columns
    assert "src:dm_payments.payment_status" in result.filter_source_columns
    assert "src:dm_payments.client_id" in result.group_source_columns
