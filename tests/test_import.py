from feature_sql_tool import FeatureSpec, FeatureSqlTool, VectorBuildRequest


def test_imports() -> None:
    assert FeatureSpec is not None
    assert FeatureSqlTool is not None
    assert VectorBuildRequest is not None
