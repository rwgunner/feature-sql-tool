from pathlib import Path

from feature_sql_tool import FeatureSpec, FeatureSqlTool


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sql_dir = project_root / "sql_samples"

    features = [
        FeatureSpec(
            feature_name="avg_payment_30d",
            sql_file_path=sql_dir / "feature_avg_payment_30d.sql",
            final_alias="avg_payment_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
        FeatureSpec(
            feature_name="cnt_paid_txn_30d",
            sql_file_path=sql_dir / "feature_cnt_paid_txn_30d.sql",
            final_alias="cnt_paid_txn_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
        FeatureSpec(
            feature_name="total_paid_amount_active_30d",
            sql_file_path=sql_dir / "feature_total_paid_active_30d.sql",
            final_alias="total_paid_amount_active_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
        FeatureSpec(
            feature_name="avg_paid_amount_recent_30d",
            sql_file_path=sql_dir / "feature_avg_paid_amount_recent_30d.sql",
            final_alias="avg_paid_amount_recent_30d",
            entity_key="client_id",
            dialect="spark",
            grain="client_id",
        ),
    ]

    tool = FeatureSqlTool()

    print("=" * 80)
    print("LINEAGE RESULTS")
    print("=" * 80)

    results = tool.analyze_features(features)
    for result in results:
        print(f"feature: {result.feature_spec.feature_name}")
        print("source_columns:", result.source_columns)
        print("value_source_columns:", result.value_source_columns)
        print("filter_source_columns:", result.filter_source_columns)
        print("join_source_columns:", result.join_source_columns)
        print("group_source_columns:", result.group_source_columns)
        print("intermediate_features:", result.intermediate_features)
        print("filter_only_intermediate_features:", result.filter_only_intermediate_features)
        print("unresolved_columns:", result.unresolved_columns)
        print("-" * 80)

    print("=" * 80)
    print("UNIFIED SQL")
    print("=" * 80)

    unified_sql = tool.build_unified_sql(features)
    print(unified_sql)

    output_path = project_root / "generated_unified_sql.sql"
    output_path.write_text(unified_sql, encoding="utf-8")
    print(f"\nSaved unified SQL to: {output_path}")


if __name__ == "__main__":
    main()
