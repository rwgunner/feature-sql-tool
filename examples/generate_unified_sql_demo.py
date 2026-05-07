from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def _print_results(title: str, results) -> None:
    print('=' * 80)
    print(title)
    print('=' * 80)
    for result in results:
        print(f"feature: {result.feature_spec.feature_name}")
        print('entity_keys:', list(result.feature_spec.entity_keys or ()))
        print('source_columns:', result.source_columns)
        print('intermediate_features:', result.intermediate_features)
        print('filter_only_intermediate_features:', result.filter_only_intermediate_features)
        print('unresolved_columns:', getattr(result, 'unresolved_columns', []))
        print('-' * 80)


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]

    client_features = [
        FeatureSpec(
            feature_name="avg_payment_30d",
            sql_file_path=base_dir / "sql_samples" / "feature_avg_payment_30d.sql",
            entity_key="client_id",
            dialect="spark",
        ),
        FeatureSpec(
            feature_name="cnt_paid_txn_30d",
            sql_file_path=base_dir / "sql_samples" / "feature_cnt_paid_txn_30d.sql",
            entity_key="client_id",
            dialect="spark",
        ),
        FeatureSpec(
            feature_name="total_paid_amount_active_30d",
            sql_file_path=base_dir / "sql_samples" / "feature_total_paid_amount_active_30d.sql",
            entity_key="client_id",
            dialect="spark",
        ),
        FeatureSpec(
            feature_name="avg_paid_amount_recent_30d",
            sql_file_path=base_dir / "sql_samples" / "feature_avg_paid_amount_recent_30d.sql",
            entity_key="client_id",
            dialect="spark",
        ),
    ]

    payment_features = [
        FeatureSpec(
            feature_name="payment_risk_score",
            sql_file_path=base_dir / "sql_samples" / "feature_payment_risk_score.sql",
            entity_keys=["client_id", "payment_id"],
            dialect="spark",
        ),
    ]

    tool = FeatureSqlTool()
    _print_results('LINEAGE RESULTS (client-level)', tool.analyze_features(client_features))
    _print_results('LINEAGE RESULTS (payment-level)', tool.analyze_features(payment_features))

    print('=' * 80)
    print('UNIFIED SQL (single-key features only)')
    print('=' * 80)
    unified_sql = tool.build_unified_sql(client_features)
    print(unified_sql)


if __name__ == '__main__':
    main()


# Optimized variant (2.0.0)
# print(tool.build_optimized_unified_sql(client_features))
