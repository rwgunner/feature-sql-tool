from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]

    features = [
        FeatureSpec(
            feature_name="avg_payment_30d",
            sql_file_path=base_dir / "sql_samples" / "feature_avg_payment_30d.sql",
            final_alias="avg_payment_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
        FeatureSpec(
            feature_name="cnt_paid_txn_30d",
            sql_file_path=base_dir / "sql_samples" / "feature_cnt_paid_txn_30d.sql",
            final_alias="cnt_paid_txn_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
        FeatureSpec(
            feature_name="total_paid_amount_active_30d",
            sql_file_path=base_dir / "sql_samples" / "feature_total_paid_active_30d.sql",
            final_alias="total_paid_amount_active_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
        FeatureSpec(
            feature_name="avg_paid_amount_recent_30d",
            sql_file_path=base_dir / "sql_samples" / "feature_avg_paid_amount_recent_30d.sql",
            final_alias="avg_paid_amount_recent_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
        FeatureSpec(
            feature_name="payment_risk_score",
            sql_file_path=base_dir / "sql_samples" / "feature_payment_risk_score.sql",
            final_alias="payment_risk_score",
            entity_keys=["client_id", "payment_id"],
            dialect="spark",
            grain="client_id,payment_id",
        ),
    ]

    tool = FeatureSqlTool()
    print('=' * 80)
    print('LINEAGE RESULTS')
    print('=' * 80)
    results = tool.analyze_features(features)
    for result in results:
        print(f"feature: {result.feature_spec.feature_name}")
        print('entity_keys:', list(result.feature_spec.entity_keys or ()))
        print('source_columns:', result.source_columns)
        print('value_source_columns:', getattr(result, 'value_source_columns', []))
        print('filter_source_columns:', getattr(result, 'filter_source_columns', []))
        print('join_source_columns:', getattr(result, 'join_source_columns', []))
        print('group_source_columns:', getattr(result, 'group_source_columns', []))
        print('intermediate_features:', result.intermediate_features)
        print('filter_only_intermediate_features:', result.filter_only_intermediate_features)
        print('unresolved_columns:', getattr(result, 'unresolved_columns', []))
        print('-' * 80)

    single_key_features = [f for f in features if len(f.entity_keys or ()) == 1]
    print('=' * 80)
    print('UNIFIED SQL (single-key features only)')
    print('=' * 80)
    unified_sql = tool.build_unified_sql(single_key_features)
    print(unified_sql)


if __name__ == '__main__':
    main()
