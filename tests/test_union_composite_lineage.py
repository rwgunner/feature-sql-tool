from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


FEATURE = FeatureSpec(
    feature_name="payment_risk_score",
    sql_file_path=Path(__file__).resolve().parents[1] / "sql_samples" / "feature_payment_risk_score.sql",
    entity_keys=["client_id", "payment_id"],
    dialect="spark",
)


def test_union_lineage_resolves_sources_without_unresolved() -> None:
    tool = FeatureSqlTool()
    result = tool.analyze_features([FEATURE])[0]

    assert result.unresolved_columns == []
    assert any(item.endswith('dm_payments_current.amount') for item in result.source_columns)
    assert any(item.endswith('dm_payments_archive.amount') for item in result.source_columns)
    assert any(item.endswith('dm_payments_current.payment_status') for item in result.source_columns)
    assert any(item.endswith('dm_payments_archive.channel') for item in result.source_columns)
    assert any(item.endswith('dm_payments_archive.payment_status') for item in result.source_columns)


def test_union_lineage_intermediate_and_group_roles() -> None:
    tool = FeatureSqlTool()
    result = tool.analyze_features([FEATURE])[0]

    assert any(item.endswith(':total_amount_30d') for item in result.intermediate_features)
    assert any(item.endswith(':payment_event_cnt_30d') for item in result.intermediate_features)
    assert any(item.endswith(':amount_bucket') for item in result.intermediate_features)
    assert any(item.endswith(':risky_payment_flag') for item in result.intermediate_features)

    assert any(item.endswith('.client_id') for item in result.group_source_columns)
    assert any(item.endswith('.payment_id') for item in result.group_source_columns)
    assert any(item.endswith('dm_payments_archive.amount') for item in result.value_source_columns)
    assert any(item.endswith('dm_payments_current.amount') for item in result.value_source_columns)
    assert result.value_source_columns


def test_composite_key_is_preserved_on_feature_spec() -> None:
    assert tuple(FEATURE.entity_keys or ()) == ("client_id", "payment_id")
    assert FEATURE.entity_key == "client_id"
