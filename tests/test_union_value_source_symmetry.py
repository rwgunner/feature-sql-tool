from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_payment_risk_score_still_returns_basic_lineage():
    base_dir = Path(__file__).resolve().parents[1]
    spec = FeatureSpec(
        feature_name="payment_risk_score",
        sql_file_path=base_dir / "sql_samples" / "feature_payment_risk_score.sql",
        entity_keys=["client_id", "payment_id"],
        dialect="spark",
    )
    result = FeatureSqlTool().analyze_features([spec])[0]
    assert result.source_columns
    assert result.intermediate_features
    assert result.unresolved_columns == []
