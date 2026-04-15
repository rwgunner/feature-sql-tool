from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool, VectorBuildRequest


def test_smoke_build_sql_from_request() -> None:
    root = Path(__file__).resolve().parents[1]
    features = [
        FeatureSpec(
            feature_name="avg_payment_30d",
            sql_file_path=root / "sql_samples" / "feature_avg_payment_30d.sql",
            final_alias="avg_payment_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
        FeatureSpec(
            feature_name="cnt_paid_txn_30d",
            sql_file_path=root / "sql_samples" / "feature_cnt_paid_txn_30d.sql",
            final_alias="cnt_paid_txn_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
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
            final_alias="avg_payment_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        )
    ]
    tool = FeatureSqlTool()
    sql = tool.build_unified_sql(features)
    assert "avg_payment_30d" in sql
