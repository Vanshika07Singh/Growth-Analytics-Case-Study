from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from growth_analytics.ab_test import analyze_ab_test, load_marketing_ab_data, recommendation_from_result, segment_effects
from growth_analytics.ga4 import calculate_funnel_dropoff, load_retention_csv


RAW_AB_PATH = ROOT / "data/raw/marketing_AB.csv"
PROCESSED_DIR = ROOT / "data/processed"


st.set_page_config(page_title="Growth Analytics Case Study", layout="wide")
st.title("Growth Analytics Case Study")
st.caption("A/B test decisioning plus ecommerce funnel and retention diagnostics.")


def format_pct(value: float) -> str:
    return f"{value:.2%}"


tab_ab, tab_ga4 = st.tabs(["A/B Test", "Funnel & Retention"])

with tab_ab:
    st.header("Marketing A/B Test")
    uploaded_file = st.file_uploader("Upload Kaggle marketing A/B CSV", type="csv")

    if uploaded_file is not None:
        ab_df = load_marketing_ab_data(uploaded_file)
    elif RAW_AB_PATH.exists():
        ab_df = load_marketing_ab_data(RAW_AB_PATH)
    else:
        ab_df = None
        st.info("Add the Kaggle CSV at `data/raw/marketing_AB.csv` or upload it here to run the analysis.")

    if ab_df is not None:
        summary, result = analyze_ab_test(ab_df)
        rec = recommendation_from_result(result)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Ad conversion", format_pct(result.ad_rate))
        col2.metric("Control conversion", format_pct(result.control_rate))
        col3.metric("Relative lift", format_pct(result.relative_lift))
        col4.metric("p-value", f"{result.p_value:.4f}")

        st.subheader("Recommendation")
        st.write(rec)

        chart_data = summary.assign(conversion_rate_pct=summary["conversion_rate"] * 100)
        fig = px.bar(
            chart_data,
            x="test_group",
            y="conversion_rate_pct",
            text="conversion_rate_pct",
            labels={"test_group": "Group", "conversion_rate_pct": "Conversion rate (%)"},
            title="Conversion Rate by Test Group",
        )
        fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Segment Diagnostics")
        segment = st.radio("Segment by", ["most_ads_day", "most_ads_hour"], horizontal=True)
        segment_df = segment_effects(ab_df, segment)
        st.dataframe(segment_df, use_container_width=True)

        segment_fig = px.line(
            segment_df,
            x=segment,
            y="relative_lift",
            markers=True,
            labels={"relative_lift": "Relative lift", segment: segment.replace("_", " ").title()},
            title="Relative Lift by Segment",
        )
        segment_fig.update_yaxes(tickformat=".1%")
        st.plotly_chart(segment_fig, use_container_width=True)

with tab_ga4:
    st.header("GA4 Funnel & Retention")
    funnel_path = PROCESSED_DIR / "ga4_funnel.csv"
    retention_path = PROCESSED_DIR / "ga4_retention.csv"

    if funnel_path.exists():
        raw_funnel = pd.read_csv(funnel_path)
        funnel = calculate_funnel_dropoff(raw_funnel[["stage", "users"]])
        leak = funnel.iloc[funnel["dropoff_rate"].fillna(0).idxmax()]

        st.metric("Biggest leak point", str(leak["stage"]), format_pct(float(leak["dropoff_rate"])))
        funnel_fig = px.funnel(
            funnel,
            x="users",
            y="stage",
            title="View to Purchase Funnel",
            labels={"users": "Users", "stage": "Stage"},
        )
        st.plotly_chart(funnel_fig, use_container_width=True)
        st.dataframe(funnel, use_container_width=True)
    else:
        st.info("Run `sql/ga4_funnel.sql` in BigQuery and export it to `data/processed/ga4_funnel.csv`.")

    if retention_path.exists():
        retention = load_retention_csv(retention_path)
        retention_fig = px.line(
            retention,
            x="days_since_first_visit",
            y="retention_rate",
            color=retention["cohort_date"].dt.strftime("%Y-%m-%d"),
            markers=True,
            labels={
                "days_since_first_visit": "Days since first visit",
                "retention_rate": "Retention rate",
                "color": "Cohort date",
            },
            title="Cohort Retention Curve",
        )
        retention_fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(retention_fig, use_container_width=True)
    else:
        st.info("Run `sql/ga4_retention.sql` in BigQuery and export it to `data/processed/ga4_retention.csv`.")

