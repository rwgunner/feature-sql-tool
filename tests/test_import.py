from feature_sql_tool import FeatureSpec, FeatureSqlToolV2, VectorBuildRequest


def test_imports() -> None:
    assert FeatureSpec is not None
    assert FeatureSqlToolV2 is not None
    assert VectorBuildRequest is not None
