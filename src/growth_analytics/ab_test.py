from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm


GROUP_AD = "ad"
GROUP_CONTROL = "psa"


@dataclass(frozen=True)
class ProportionResult:
    ad_conversions: int
    ad_users: int
    control_conversions: int
    control_users: int
    ad_rate: float
    control_rate: float
    absolute_lift: float
    relative_lift: float
    z_stat: float
    p_value: float
    relative_lift_ci_low: float
    relative_lift_ci_high: float


def load_marketing_ab_data(path: str | Path) -> pd.DataFrame:
    """Load and normalize the Kaggle marketing A/B test CSV."""
    df = pd.read_csv(path)
    df = df.rename(columns=lambda col: col.strip().lower().replace(" ", "_"))

    expected = {"test_group", "converted", "total_ads", "most_ads_day", "most_ads_hour"}
    missing = expected.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    normalized = df.copy()
    normalized["test_group"] = normalized["test_group"].str.lower().str.strip()
    normalized["converted"] = normalized["converted"].astype(bool).astype(int)
    normalized["most_ads_hour"] = normalized["most_ads_hour"].astype(int)
    return normalized


def summarize_conversion_by_group(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby("test_group", as_index=False)
        .agg(users=("converted", "size"), conversions=("converted", "sum"), avg_ads_seen=("total_ads", "mean"))
        .assign(conversion_rate=lambda frame: frame["conversions"] / frame["users"])
        .sort_values("test_group")
    )
    return summary


def two_proportion_z_test(
    ad_conversions: int,
    ad_users: int,
    control_conversions: int,
    control_users: int,
    alpha: float = 0.05,
) -> ProportionResult:
    """Run a two-sided two-proportion z-test and relative lift confidence interval."""
    if min(ad_users, control_users) <= 0:
        raise ValueError("Both groups must contain at least one user.")

    ad_rate = ad_conversions / ad_users
    control_rate = control_conversions / control_users
    pooled_rate = (ad_conversions + control_conversions) / (ad_users + control_users)
    pooled_se = np.sqrt(pooled_rate * (1 - pooled_rate) * (1 / ad_users + 1 / control_users))

    z_stat = (ad_rate - control_rate) / pooled_se
    p_value = 2 * (1 - norm.cdf(abs(z_stat)))

    absolute_lift = ad_rate - control_rate
    relative_lift = (ad_rate / control_rate) - 1

    # Delta method for log risk ratio, reported back as relative lift bounds.
    z_crit = norm.ppf(1 - alpha / 2)
    log_rr = np.log(ad_rate / control_rate)
    log_rr_se = np.sqrt((1 / ad_conversions) - (1 / ad_users) + (1 / control_conversions) - (1 / control_users))
    relative_lift_ci_low = np.exp(log_rr - z_crit * log_rr_se) - 1
    relative_lift_ci_high = np.exp(log_rr + z_crit * log_rr_se) - 1

    return ProportionResult(
        ad_conversions=int(ad_conversions),
        ad_users=int(ad_users),
        control_conversions=int(control_conversions),
        control_users=int(control_users),
        ad_rate=float(ad_rate),
        control_rate=float(control_rate),
        absolute_lift=float(absolute_lift),
        relative_lift=float(relative_lift),
        z_stat=float(z_stat),
        p_value=float(p_value),
        relative_lift_ci_low=float(relative_lift_ci_low),
        relative_lift_ci_high=float(relative_lift_ci_high),
    )


def analyze_ab_test(df: pd.DataFrame) -> tuple[pd.DataFrame, ProportionResult]:
    summary = summarize_conversion_by_group(df)
    indexed = summary.set_index("test_group")

    missing_groups = {GROUP_AD, GROUP_CONTROL}.difference(indexed.index)
    if missing_groups:
        raise ValueError(f"Missing test groups: {', '.join(sorted(missing_groups))}")

    result = two_proportion_z_test(
        ad_conversions=int(indexed.loc[GROUP_AD, "conversions"]),
        ad_users=int(indexed.loc[GROUP_AD, "users"]),
        control_conversions=int(indexed.loc[GROUP_CONTROL, "conversions"]),
        control_users=int(indexed.loc[GROUP_CONTROL, "users"]),
    )
    return summary, result


def segment_effects(df: pd.DataFrame, segment_col: str) -> pd.DataFrame:
    """Calculate segment-level conversion rates and lift for day/hour diagnostics."""
    segment_summary = (
        df.groupby([segment_col, "test_group"], as_index=False)
        .agg(users=("converted", "size"), conversions=("converted", "sum"))
        .assign(conversion_rate=lambda frame: frame["conversions"] / frame["users"])
    )

    pivot = segment_summary.pivot(index=segment_col, columns="test_group", values=["users", "conversions", "conversion_rate"])
    pivot.columns = [f"{metric}_{group}" for metric, group in pivot.columns]
    pivot = pivot.reset_index()
    pivot["absolute_lift"] = pivot[f"conversion_rate_{GROUP_AD}"] - pivot[f"conversion_rate_{GROUP_CONTROL}"]
    pivot["relative_lift"] = (pivot[f"conversion_rate_{GROUP_AD}"] / pivot[f"conversion_rate_{GROUP_CONTROL}"]) - 1
    return pivot.sort_values(segment_col)


def recommendation_from_result(result: ProportionResult, alpha: float = 0.05) -> str:
    lift_pct = result.relative_lift * 100
    ci_low = result.relative_lift_ci_low * 100
    ci_high = result.relative_lift_ci_high * 100

    if result.p_value < alpha and result.relative_lift > 0:
        decision = "Ship the ad experience"
    elif result.p_value < alpha and result.relative_lift <= 0:
        decision = "Do not ship the ad experience"
    else:
        decision = "Test longer before shipping"

    return (
        f"{decision}. The ad group converted at {result.ad_rate:.2%} versus "
        f"{result.control_rate:.2%} for PSA control, a relative lift of {lift_pct:.2f}% "
        f"(95% CI: {ci_low:.2f}% to {ci_high:.2f}%, p={result.p_value:.4f})."
    )

