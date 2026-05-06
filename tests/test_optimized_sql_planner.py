from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def test_build_optimized_unified_sql_merges_deposit_features():
    base_dir = Path(__file__).resolve().parents[1] / 'sql_samples'
    tool = FeatureSqlTool()
    features = [
        FeatureSpec(feature_name='cnt_dep_act', sql_file_path=base_dir / 'feature_cnt_dep_act.sql', entity_key='client_id', dialect='spark'),
        FeatureSpec(feature_name='sum_dep_now', sql_file_path=base_dir / 'feature_sum_dep_now.sql', entity_key='client_id', dialect='spark'),
    ]
    sql = tool.build_optimized_unified_sql(features)
    assert 'base_' in sql
    assert 'agg_' in sql
    assert 'cnt_dep_act' in sql
    assert 'sum_dep_now' in sql
