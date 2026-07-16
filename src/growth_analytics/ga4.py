from __future__ import annotations

from pathlib import Path

import pandas as pd


FUNNEL_STAGES = ["view_item", "add_to_cart", "begin_checkout", "purchase"]


def load_funnel_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"stage", "users"}
    missing = expected.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    return calculate_funnel_dropoff(df)


def calculate_funnel_dropoff(funnel: pd.DataFrame) -> pd.DataFrame:
    ordered = funnel.copy()
    ordered["stage"] = pd.Categorical(ordered["stage"], categories=FUNNEL_STAGES, ordered=True)
    ordered = ordered.sort_values("stage").reset_index(drop=True)
    ordered["previous_users"] = ordered["users"].shift(1)
    ordered["step_conversion_rate"] = ordered["users"] / ordered["previous_users"]
    ordered.loc[0, "step_conversion_rate"] = 1.0
    ordered["dropoff_users"] = ordered["previous_users"] - ordered["users"]
    ordered.loc[0, "dropoff_users"] = 0
    ordered["dropoff_rate"] = 1 - ordered["step_conversion_rate"]
    return ordered


def biggest_leak(funnel: pd.DataFrame) -> pd.Series:
    calculated = calculate_funnel_dropoff(funnel)
    return calculated.iloc[calculated["dropoff_rate"].fillna(0).idxmax()]


def load_retention_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["cohort_date"])
    expected = {"cohort_date", "days_since_first_visit", "cohort_users", "retained_users"}
    missing = expected.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    df["retention_rate"] = df["retained_users"] / df["cohort_users"]
    return df.sort_values(["cohort_date", "days_since_first_visit"])

