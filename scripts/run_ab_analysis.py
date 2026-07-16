from __future__ import annotations

import argparse
from pathlib import Path

from growth_analytics.ab_test import (
    analyze_ab_test,
    load_marketing_ab_data,
    recommendation_from_result,
    segment_effects,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the marketing A/B test analysis.")
    parser.add_argument("--input", default="data/raw/marketing_AB.csv", help="Path to Kaggle marketing A/B test CSV.")
    parser.add_argument("--output-dir", default="data/processed", help="Directory for processed outputs.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_marketing_ab_data(args.input)
    summary, result = analyze_ab_test(df)
    by_day = segment_effects(df, "most_ads_day")
    by_hour = segment_effects(df, "most_ads_hour")

    summary.to_csv(output_dir / "ab_summary.csv", index=False)
    by_day.to_csv(output_dir / "ab_by_day.csv", index=False)
    by_hour.to_csv(output_dir / "ab_by_hour.csv", index=False)
    (output_dir / "ab_recommendation.txt").write_text(recommendation_from_result(result), encoding="utf-8")

    print(recommendation_from_result(result))


if __name__ == "__main__":
    main()

