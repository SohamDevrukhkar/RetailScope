"""
Page 2 — Sales & Purchase Trends
Time-based analysis of revenue, orders, and purchasing patterns.
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
    configure_page, render_page_header, get_spark, load_order_metrics,
    section_header, apply_chart_theme, no_data_msg,
    render_date_filters, filter_by_dates,
    pipeline_not_run_error, check_processed_data,
    data_source_badge, PLOTLY_COLORS, kpi_card,
)

configure_page("Sales & Purchase Trends", "📈")

if not check_processed_data():
    pipeline_not_run_error()
    st.stop()

spark = get_spark()
om = load_order_metrics(spark)
om["purchase_date"] = pd.to_datetime(om["purchase_date"])

# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### 🔧 Trend Controls")
start, end = render_date_filters(om)

granularity = st.sidebar.radio("Aggregation Interval", ["Monthly", "Daily", "Yearly"], index=0)

fom = filter_by_dates(om, start, end)

render_page_header(
    title="Sales & Purchase Trends",
    subtitle="Macro and micro temporal dynamics · Longitudinal revenue trajectories, hour-of-day patterns, and seasonal cycles",
    icon="📈",
    date_range=(start, end),
    badge_text="Temporal Intelligence",
)

if fom.empty:
    no_data_msg()
    st.stop()

# ── Aggregate by granularity ────────────────────────────────────────────────
if granularity == "Daily":
    grp = fom.groupby("purchase_date").agg(
        revenue=("product_revenue", "sum"),
        orders=("order_id", "nunique"),
    ).reset_index().rename(columns={"purchase_date": "Period"})
elif granularity == "Monthly":
    grp = fom.groupby("purchase_year_month").agg(
        revenue=("product_revenue", "sum"),
        orders=("order_id", "nunique"),
    ).reset_index().rename(columns={"purchase_year_month": "Period"})
else:
    grp = fom.groupby("purchase_year").agg(
        revenue=("product_revenue", "sum"),
        orders=("order_id", "nunique"),
    ).reset_index().rename(columns={"purchase_year": "Period"})

grp = grp.sort_values("Period")
grp["avg_order_value"] = grp["revenue"] / grp["orders"]

# ── Best/worst months ───────────────────────────────────────────────────────
monthly = fom.groupby("purchase_year_month").agg(
    revenue=("product_revenue", "sum"),
    orders=("order_id", "nunique"),
).reset_index().sort_values("revenue", ascending=False)

best_month = monthly.iloc[0] if not monthly.empty else None
worst_month = monthly.iloc[-1] if not monthly.empty else None

section_header("Interval Highlights", icon="⚡")
k1, k2, k3, k4 = st.columns(4)
with k1:
    period_start = str(grp['Period'].iloc[0])[:10]
    period_end = str(grp['Period'].iloc[-1])[:10]
    kpi_card("Active Time Span", f"{period_start} → {period_end}", delta=f"{len(grp)} {granularity} periods", color="#2563EB", icon="📆")
with k2:
    kpi_card("Period Total Revenue", f"R$ {grp['revenue'].sum():,.0f}", delta=f"{grp['orders'].sum():,} total orders", color="#0D9488", icon="💰")
with k3:
    if best_month is not None:
        kpi_card("Peak Revenue Month", f"{best_month['purchase_year_month']}", delta=f"R$ {best_month['revenue']:,.0f} ({best_month['orders']:,} orders)", color="#F59E0B", icon="🚀")
with k4:
    if worst_month is not None:
        kpi_card("Trough Revenue Month", f"{worst_month['purchase_year_month']}", delta=f"R$ {worst_month['revenue']:,.0f} ({worst_month['orders']:,} orders)", color="#EF4444", icon="📉")

st.markdown("<br>", unsafe_allow_html=True)

# ── Revenue trend ─────────────────────────────────────────────────────────────
section_header(f"{granularity} Revenue Trajectory", icon="📊")
fig1 = go.Figure()
fig1.add_trace(go.Scatter(
    x=grp["Period"], y=grp["revenue"],
    mode="lines+markers", name="Revenue",
    line=dict(color="#2563EB", width=2.5),
    fill="tozeroy", fillcolor="rgba(37, 99, 235, 0.08)",
    hovertemplate="<b>%{x}</b><br>Revenue: R$ %{y:,.2f}<extra></extra>",
))
fig1 = apply_chart_theme(fig1, f"{granularity} Product Revenue (R$)", height=380)
fig1.update_xaxes(tickangle=45)
st.plotly_chart(fig1, use_container_width=True)

# ── Orders & Avg Order Value ──────────────────────────────────────────────────
section_header(f"{granularity} Order Volume & Average Order Value (AOV)", icon="🏷️")
c1, c2 = st.columns(2)
with c1:
    fig2 = px.bar(
        grp, x="Period", y="orders",
        color_discrete_sequence=["#0D9488"],
        labels={"orders": "Distinct Orders Placed", "Period": "Period"},
    )
    fig2.update_traces(hovertemplate="<b>%{x}</b><br>Orders: %{y:,}<extra></extra>")
    fig2 = apply_chart_theme(fig2, f"{granularity} Order Volume", height=350)
    fig2.update_xaxes(tickangle=45)
    st.plotly_chart(fig2, use_container_width=True)

with c2:
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=grp["Period"], y=grp["avg_order_value"],
        mode="lines+markers", name="Avg Order Value",
        line=dict(color="#F59E0B", width=2.5),
        hovertemplate="<b>%{x}</b><br>AOV: R$ %{y:,.2f}<extra></extra>",
    ))
    fig3 = apply_chart_theme(fig3, f"{granularity} Average Order Value (R$)", height=350)
    fig3.update_xaxes(tickangle=45)
    st.plotly_chart(fig3, use_container_width=True)

# ── Weekday patterns ─────────────────────────────────────────────────────────
section_header("Purchasing Cycles by Day of Week", icon="📅")

day_map = {1: "Sunday", 2: "Monday", 3: "Tuesday", 4: "Wednesday", 5: "Thursday", 6: "Friday", 7: "Saturday"}
wday = fom.groupby("purchase_day_of_week").agg(
    revenue=("product_revenue", "sum"),
    orders=("order_id", "nunique"),
).reset_index()
wday["day_name"] = wday["purchase_day_of_week"].map(day_map)
wday = wday.sort_values("purchase_day_of_week")

c1, c2 = st.columns(2)
with c1:
    fig4 = px.bar(
        wday, x="day_name", y="orders",
        color_discrete_sequence=["#2563EB"],
        labels={"day_name": "Day of Week", "orders": "Orders"},
    )
    fig4.update_traces(hovertemplate="<b>%{x}</b><br>Orders: %{y:,}<extra></extra>")
    fig4 = apply_chart_theme(fig4, "Order Volume by Day of Week", height=340)
    st.plotly_chart(fig4, use_container_width=True)

with c2:
    fig5 = px.bar(
        wday, x="day_name", y="revenue",
        color_discrete_sequence=["#0D9488"],
        labels={"day_name": "Day of Week", "revenue": "Revenue (R$)"},
    )
    fig5.update_traces(hovertemplate="<b>%{x}</b><br>Revenue: R$ %{y:,.2f}<extra></extra>")
    fig5 = apply_chart_theme(fig5, "Revenue by Day of Week", height=340)
    st.plotly_chart(fig5, use_container_width=True)

# ── Hour of day ───────────────────────────────────────────────────────────────
section_header("Hourly Purchasing Distribution (24-Hour Cycle)", icon="⏰")
hourly = fom.groupby("purchase_hour").agg(
    orders=("order_id", "nunique"),
    revenue=("product_revenue", "sum"),
).reset_index()

fig6 = px.bar(
    hourly, x="purchase_hour", y="orders",
    color_discrete_sequence=["#8B5CF6"],
    labels={"purchase_hour": "Hour of Day (00:00 – 23:00, Brasília Time)", "orders": "Orders Placed"},
)
fig6.update_traces(hovertemplate="<b>Hour %{x}:00</b><br>Orders: %{y:,}<extra></extra>")
fig6 = apply_chart_theme(fig6, "Order Volume by Hour of Day", height=340)
fig6.update_xaxes(dtick=1)
st.plotly_chart(fig6, use_container_width=True)

# ── Monthly revenue by year (seasonal view) ──────────────────────────────────
section_header("Year-over-Year Seasonal Revenue Comparison", icon="🍂")
fom["month_num"] = fom["purchase_date"].dt.month
monthly_yr = fom.groupby(["purchase_year", "month_num"]).agg(
    revenue=("product_revenue", "sum"),
).reset_index()
monthly_yr["Month"] = monthly_yr["month_num"].map({
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
})
monthly_yr["purchase_year"] = monthly_yr["purchase_year"].astype(str)

fig7 = px.line(
    monthly_yr, x="Month", y="revenue", color="purchase_year",
    markers=True,
    labels={"revenue": "Revenue (R$)", "purchase_year": "Year"},
    color_discrete_sequence=PLOTLY_COLORS,
)
fig7.update_traces(hovertemplate="<b>%{x} %{data.name}</b><br>Revenue: R$ %{y:,.2f}<extra></extra>")
fig7 = apply_chart_theme(fig7, "Monthly Revenue Seasonality Across Years", height=380)
fig7.update_layout(
    xaxis=dict(categoryorder="array", categoryarray=[
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ])
)
st.plotly_chart(fig7, use_container_width=True)

data_source_badge()
