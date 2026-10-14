"""
Page 3 — Customer Analytics & RFM Segmentation
Customer lifetime value, repeat purchasing, and behavioral RFM segmentation.
"""
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.ui_utils import (
    configure_page, render_page_header, get_spark, load_customer_rfm, load_order_metrics,
    kpi_card, section_header, apply_chart_theme, no_data_msg,
    pipeline_not_run_error, check_processed_data,
    data_source_badge, PLOTLY_COLORS,
)
from src.customer_segmentation import SEGMENT_DESCRIPTIONS, RFM_SCORING_EXPLANATION

configure_page("Customer Analytics", "👥")

if not check_processed_data():
    pipeline_not_run_error()
    st.stop()

spark = get_spark()
rfm = load_customer_rfm(spark)
om = load_order_metrics(spark)

rfm["last_purchase_date"] = pd.to_datetime(rfm["last_purchase_date"])
rfm["first_purchase_date"] = pd.to_datetime(rfm["first_purchase_date"])

# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### 🔧 Customer Filters")
all_segments = sorted(rfm["segment"].dropna().unique())
seg_filter = st.sidebar.multiselect("Customer Segment", all_segments, placeholder="All segments")
all_states = sorted(rfm["customer_state"].dropna().unique())
state_filter = st.sidebar.multiselect("Customer State", all_states, placeholder="All states")

frf = rfm.copy()
if seg_filter:
    frf = frf[frf["segment"].isin(seg_filter)]
if state_filter:
    frf = frf[frf["customer_state"].isin(state_filter)]

render_page_header(
    title="Customer Analytics & RFM Segmentation",
    subtitle="Behavioral cohort intelligence · Recency, Frequency, and Monetary (RFM) modeling using unique customer identifiers",
    icon="👥",
    badge_text="customer_unique_id Resolution",
)

if frf.empty:
    no_data_msg()
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────────
section_header("Cohort Performance Metrics", icon="💎")

total = len(frf)
repeat = frf[frf["is_repeat"] == True]
onetime = frf[frf["is_repeat"] == False]
repeat_rate = (len(repeat) / total * 100) if total > 0 else 0.0
avg_spend = frf["monetary"].mean()
avg_freq = frf["frequency"].mean()
avg_recency = frf["recency"].mean()

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    kpi_card("Total Customers", f"{total:,}", delta="Distinct individuals", color="#2563EB", icon="👥")
with k2:
    kpi_card("Repeat Customers", f"{len(repeat):,}", delta="> 1 distinct order", color="#0D9488", icon="🔁")
with k3:
    kpi_card("One-Time Buyers", f"{len(onetime):,}", delta=f"{100 - repeat_rate:.1f}% of cohort", color="#F59E0B", icon="👤")
with k4:
    kpi_card("Repeat Purchase Rate", f"{repeat_rate:.1f}%", delta="Benchmark: ~3.0% (Olist)", color="#8B5CF6", icon="📈")
with k5:
    kpi_card("Avg Spend / Customer", f"R$ {avg_spend:,.2f}", delta="Cumulative lifetime spend", color="#10B981", icon="💳")
with k6:
    kpi_card("Avg Recency", f"{avg_recency:.0f} days", delta="Days since last purchase", color="#EC4899", icon="⏳")

st.markdown("<br>", unsafe_allow_html=True)

# ── Segment distribution ─────────────────────────────────────────────────────
section_header("RFM Behavioral Segmentation", icon="🎯")

with st.expander("ℹ️ Transparent RFM Methodology & Scoring Rules", expanded=False):
    st.markdown(RFM_SCORING_EXPLANATION)
    st.markdown("**Segment Definitions & Strategy:**")
    for seg, desc in SEGMENT_DESCRIPTIONS.items():
        st.markdown(f"- **{seg}:** {desc}")

seg_counts = frf.groupby("segment").agg(
    customers=("customer_unique_id", "count"),
    total_revenue=("monetary", "sum"),
    avg_spend=("monetary", "mean"),
    avg_recency=("recency", "mean"),
    avg_frequency=("frequency", "mean"),
).reset_index().sort_values("customers", ascending=False)

c1, c2 = st.columns(2)
with c1:
    # High-contrast donut without overlapping labels
    fig1 = px.pie(
        seg_counts,
        names="segment",
        values="customers",
        color="segment",
        color_discrete_sequence=PLOTLY_COLORS,
        hole=0.45,
    )
    fig1.update_traces(
        textposition="inside",
        textinfo="percent",
        hovertemplate="<b>Segment: %{label}</b><br>Customers: %{value:,}<br>Share: %{percent}<extra></extra>",
    )
    fig1 = apply_chart_theme(fig1, "Customer Share by RFM Segment", height=380)
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    fig2 = px.bar(
        seg_counts.sort_values("total_revenue", ascending=True),
        x="total_revenue",
        y="segment",
        orientation="h",
        color_discrete_sequence=["#2563EB"],
        labels={"total_revenue": "Total Segment Revenue (R$)", "segment": "Segment"},
    )
    fig2.update_traces(
        hovertemplate="<b>%{y}</b><br>Revenue: R$ %{x:,.2f}<extra></extra>"
    )
    fig2 = apply_chart_theme(fig2, "Revenue Contribution by RFM Segment", height=380)
    fig2.update_layout(margin=dict(l=10, r=20, t=50, b=30))
    st.plotly_chart(fig2, use_container_width=True)

# Segment summary table with readable formatting
st.dataframe(
    seg_counts.rename(columns={
        "segment": "Segment",
        "customers": "Customer Count",
        "total_revenue": "Total Revenue (R$)",
        "avg_spend": "Avg Spend per Customer",
        "avg_recency": "Avg Recency (Days)",
        "avg_frequency": "Avg Frequency (Orders)",
    }).style.format({
        "Customer Count": "{:,}",
        "Total Revenue (R$)": "R$ {:,.2f}",
        "Avg Spend per Customer": "R$ {:,.2f}",
        "Avg Recency (Days)": "{:.0f}",
        "Avg Frequency (Orders)": "{:.2f}",
    }),
    use_container_width=True,
    hide_index=True,
)

# ── RFM score scatter ────────────────────────────────────────────────────────
section_header("RFM Score Scatter (Recency vs. Monetary)", icon="🔬")

sample_n = min(4000, len(frf))
sample = frf.sample(sample_n, random_state=42)

fig3 = px.scatter(
    sample,
    x="recency",
    y="monetary",
    color="segment",
    size="frequency",
    size_max=16,
    opacity=0.70,
    color_discrete_sequence=PLOTLY_COLORS,
    labels={
        "recency": "Recency (Days Since Last Order)",
        "monetary": "Monetary (Total Spend R$)",
        "frequency": "Order Frequency",
        "segment": "Segment",
    },
    hover_data={
        "customer_state": True,
        "r_score": True,
        "f_score": True,
        "m_score": True,
        "recency": ":.0f",
        "monetary": ":,.2f",
    },
)
fig3 = apply_chart_theme(fig3, f"Recency vs. Monetary Distribution (Sample of {sample_n:,} Customers)", height=420)
st.plotly_chart(fig3, use_container_width=True)

# ── Repeat vs one-time ────────────────────────────────────────────────────────
section_header("Repeat vs. One-Time Customer Economic Impact", icon="⚖️")

rov = frf.groupby("is_repeat").agg(
    monetary=("monetary", "sum"),
    customers=("customer_unique_id", "count"),
).reset_index()
rov["Type"] = rov["is_repeat"].map({True: "Repeat Customers (>1 order)", False: "One-Time Customers (1 order)"})
rov["RevShare"] = (rov["monetary"] / rov["monetary"].sum() * 100).round(1)
rov["CustShare"] = (rov["customers"] / rov["customers"].sum() * 100).round(1)

c1, c2 = st.columns(2)
with c1:
    fig5 = px.bar(
        rov,
        x="Type",
        y="monetary",
        color="Type",
        color_discrete_sequence=["#F59E0B", "#0D9488"],
        labels={"monetary": "Total Product Revenue (R$)", "Type": ""},
    )
    fig5.update_traces(
        hovertemplate="<b>%{x}</b><br>Revenue: R$ %{y:,.2f}<extra></extra>"
    )
    fig5 = apply_chart_theme(fig5, "Total Revenue: Repeat vs. One-Time", height=340)
    fig5.update_layout(showlegend=False)
    st.plotly_chart(fig5, use_container_width=True)

with c2:
    fig6 = px.bar(
        rov,
        x="Type",
        y="customers",
        color="Type",
        color_discrete_sequence=["#F59E0B", "#0D9488"],
        labels={"customers": "Unique Customer Count", "Type": ""},
    )
    fig6.update_traces(
        hovertemplate="<b>%{x}</b><br>Customers: %{y:,}<extra></extra>"
    )
    fig6 = apply_chart_theme(fig6, "Customer Volume: Repeat vs. One-Time", height=340)
    fig6.update_layout(showlegend=False)
    st.plotly_chart(fig6, use_container_width=True)

# ── Top 20 customers ──────────────────────────────────────────────────────────
section_header("Top 20 Customers by Cumulative Spending", icon="🏆")

top20 = (
    frf.sort_values("monetary", ascending=False)
    .head(20)[[
        "customer_unique_id", "monetary", "frequency", "recency",
        "segment", "customer_state", "customer_city", "last_purchase_date",
    ]]
    .reset_index(drop=True)
)
top20.index += 1

st.dataframe(
    top20.rename(columns={
        "customer_unique_id": "Customer Unique ID",
        "monetary": "Cumulative Spend (R$)",
        "frequency": "Orders",
        "recency": "Recency (Days)",
        "segment": "RFM Segment",
        "customer_state": "State",
        "customer_city": "City",
        "last_purchase_date": "Last Order Date",
    }).style.format({
        "Cumulative Spend (R$)": "R$ {:,.2f}",
        "Orders": "{:.0f}",
        "Recency (Days)": "{:.0f}",
    }),
    use_container_width=True,
)

# ── Searchable customer table ─────────────────────────────────────────────────
section_header("Search Customer Cohort", icon="🔍")
search_id = st.text_input("Search by Customer Unique ID (prefix or substring)", placeholder="e.g. 0a52f3...")
display_df = frf.copy()

if search_id and search_id.strip():
    display_df = display_df[display_df["customer_unique_id"].str.contains(
        search_id.strip(), case=False, na=False
    )]

st.markdown(f"Displaying **{min(len(display_df), 100):,}** of **{len(display_df):,}** matching customers:")
st.dataframe(
    display_df[[
        "customer_unique_id", "monetary", "frequency", "recency",
        "r_score", "f_score", "m_score", "segment",
        "customer_state", "last_purchase_date",
    ]]
    .sort_values("monetary", ascending=False)
    .head(100)
    .rename(columns={
        "customer_unique_id": "Customer Unique ID",
        "monetary": "Total Spend (R$)",
        "frequency": "Orders",
        "recency": "Recency",
        "r_score": "R",
        "f_score": "F",
        "m_score": "M",
        "segment": "Segment",
        "customer_state": "State",
        "last_purchase_date": "Last Purchase",
    }).style.format({
        "Total Spend (R$)": "R$ {:,.2f}",
        "Orders": "{:.0f}",
        "Recency": "{:.0f}",
    }),
    use_container_width=True,
    hide_index=True,
)

data_source_badge()
