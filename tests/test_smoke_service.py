from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool, VectorBuildRequest


def test_smoke_build_sql_from_request() -> None:
    root = Path(__file__).resolve().parents[1]
    features = [
        FeatureSpec(
            feature_name="avg_payment_30d",
            sql_file_path=root / "sql_samples" / "feature_avg_payment_30d.sql",
            entity_key="client_id",
            dialect="spark",
        ),
        FeatureSpec(
            feature_name="cnt_paid_txn_30d",
            sql_file_path=root / "sql_samples" / "feature_cnt_paid_txn_30d.sql",
            entity_key="client_id",
            dialect="spark",
        ),
    ]
    tool = FeatureSqlTool()
    request = VectorBuildRequest(features=features, entity_key="client_id")
    sql = tool.build_unified_sql(request)
    assert "WITH" in sql
    assert "entity_base" in sql


def test_smoke_build_sql_from_feature_list() -> None:
    root = Path(__file__).resolve().parents[1]
    features = [
        FeatureSpec(
            feature_name="avg_payment_30d",
            sql_file_path=root / "sql_samples" / "feature_avg_payment_30d.sql",
            entity_key="client_id",
            dialect="spark",
        )
    ]
    tool = FeatureSqlTool()
    sql = tool.build_unified_sql(features)
    assert "avg_payment_30d" in sql


def test_composite_key_build_sql_not_supported_yet() -> None:
    root = Path(__file__).resolve().parents[1]
    features = [
        FeatureSpec(
            feature_name="payment_risk_score",
            sql_file_path=root / "sql_samples" / "feature_payment_risk_score.sql",
            entity_keys=["client_id", "payment_id"],
            dialect="spark",
        )
    ]
    tool = FeatureSqlTool()
    try:
        tool.build_unified_sql(features)
    except NotImplementedError:
        return
    raise AssertionError('Composite-key unified SQL generation should raise NotImplementedError for 1.1.0')


def test_analyze_features_requires_same_entity_keys() -> None:
    root = Path(__file__).resolve().parents[1]
    features = [
        FeatureSpec(feature_name="avg_payment_30d", sql_file_path=root / "sql_samples" / "feature_avg_payment_30d.sql", entity_key="client_id", dialect="spark"),
        FeatureSpec(feature_name="payment_risk_score", sql_file_path=root / "sql_samples" / "feature_payment_risk_score.sql", entity_keys=["client_id", "payment_id"], dialect="spark"),
    ]
    tool = FeatureSqlTool()
    try:
        tool.analyze_features(features)
    except ValueError as exc:
        assert 'same entity_keys' in str(exc)
        return
    raise AssertionError('Mixed-grain analyze_features should raise ValueError for 1.1.0')
