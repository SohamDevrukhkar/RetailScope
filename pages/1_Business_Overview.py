"""
Page 1 — Business Overview
Executive summary of revenue, customer volume, and operational performance.
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
    configure_page, render_page_header, get_spark, load_order_metrics, load_item_data,
    kpi_card, section_header, apply_chart_theme, format_brl,
    format_category_name, format_product_label,
    render_date_filters, filter_by_dates, no_data_msg,
    pipeline_not_run_error, check_processed_data, data_source_badge,
    PLOTLY_COLORS, PALETTE,
)

configure_page("Business Overview", "📊")

if not check_processed_data():
    pipeline_not_run_error()
    st.stop()

# ── Load data ────────────────────────────────────────────────────────────────
spark = get_spark()
om = load_order_metrics(spark)
items = load_item_data(spark)

om["purchase_date"] = pd.to_datetime(om["purchase_date"])
items["purchase_date"] = pd.to_datetime(items["purchase_date"])

# ── Sidebar filters ──────────────────────────────────────────────────────────
st.sidebar.markdown("### 🔧 Overview Filters")
start, end = render_date_filters(om)

all_states = sorted(om["customer_state"].dropna().unique())
state_filter = st.sidebar.multiselect("Customer State", all_states, placeholder="All states")

all_statuses = sorted(om["order_status"].dropna().unique())
status_filter = st.sidebar.multiselect("Order Status", all_statuses, placeholder="All statuses")

all_cats = sorted(om["primary_category"].dropna().unique())
all_cats_formatted = {c: format_category_name(c) for c in all_cats}
cat_filter_selected = st.sidebar.multiselect(
    "Product Category",
    options=all_cats,
    format_func=lambda x: all_cats_formatted.get(x, x),
    placeholder="All categories",
)

# ── Apply filters ────────────────────────────────────────────────────────────
fom = filter_by_dates(om, start, end)
if state_filter:
    fom = fom[fom["customer_state"].isin(state_filter)]
if status_filter:
    fom = fom[fom["order_status"].isin(status_filter)]
if cat_filter_selected:
    fom = fom[fom["primary_category"].isin(cat_filter_selected)]

fitems = filter_by_dates(items, start, end)
if state_filter:
    fitems = fitems[fitems["customer_state"].isin(state_filter)]
if cat_filter_selected:
    fitems = fitems[fitems["category_english"].isin(cat_filter_selected)]

# ── Header ───────────────────────────────────────────────────────────────────
render_page_header(
    title="Business Overview",
    subtitle="RetailScope Executive Intelligence · Macro transaction metrics from Brazilian e-commerce (Olist)",
    icon="📊",
    date_range=(start, end),
    badge_text="100% Processed Data",
)

if fom.empty:
    no_data_msg()
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────────
section_header("Executive Key Performance Indicators", icon="💎")

total_rev = fom["product_revenue"].sum()
total_orders = fom["order_id"].nunique()
total_customers = fom["customer_unique_id"].nunique()
avg_ov = fom["product_revenue"].mean()
avg_review = fom["review_score"].mean()

repeat_mask = fom.groupby("customer_unique_id")["order_id"].transform("nunique") > 1
repeat_customers = fom[repeat_mask]["customer_unique_id"].nunique()
repeat_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    kpi_card("Total Product Revenue", f"R$ {total_rev:,.0f}", delta="Excluding freight", color="#2563EB", icon="💰")
with k2:
    kpi_card("Total Orders", f"{total_orders:,}", delta=f"{len(fom):,} line items", color="#0D9488", icon="📦")
with k3:
    kpi_card("Unique Customers", f"{total_customers:,}", delta="by customer_unique_id", color="#F59E0B", icon="👥")
with k4:
    kpi_card("Avg Order Value (AOV)", f"R$ {avg_ov:,.2f}", delta="per distinct order", color="#8B5CF6", icon="🏷️")
with k5:
    kpi_card("Repeat Customer Rate", f"{repeat_rate:.1f}%", delta=f"{repeat_customers:,} repeat buyers", color="#10B981", icon="🔄")
with k6:
    score = avg_review if not pd.isna(avg_review) else 0.0
    kpi_card("Avg Review Score", f"{score:.2f} ★", delta="Scale 1.0 – 5.0", color="#EC4899", icon="⭐")

st.markdown("<br>", unsafe_allow_html=True)

# ── Revenue & Orders trend ────────────────────────────────────────────────────
section_header("Time-Series Trajectory", icon="📈")

monthly = (
    fom.groupby("purchase_year_month")
    .agg(revenue=("product_revenue", "sum"), orders=("order_id", "nunique"))
    .reset_index()
    .rename(columns={"purchase_year_month": "Month"})
    .sort_values("Month")
)

c1, c2 = st.columns(2)
with c1:
    if not monthly.empty:
        fig1 = go.Figure()
        fig1.add_trace(
            go.Scatter(
                x=monthly["Month"],
                y=monthly["revenue"],
                mode="lines+markers",
                name="Revenue",
                line=dict(color="#2563EB", width=2.5),
                fill="tozeroy",
                fillcolor="rgba(37, 99, 235, 0.08)",
                hovertemplate="<b>%{x}</b><br>Revenue: R$ %{y:,.2f}<extra></extra>",
            )
        )
        fig1 = apply_chart_theme(fig1, "Monthly Product Revenue (R$)", height=350)
        fig1.update_xaxes(tickangle=45)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        no_data_msg()

with c2:
    if not monthly.empty:
        fig2 = px.bar(
            monthly,
            x="Month",
            y="orders",
            labels={"orders": "Orders Placed", "Month": "Month"},
            color_discrete_sequence=["#0D9488"],
        )
        fig2.update_traces(hovertemplate="<b>%{x}</b><br>Orders: %{y:,}<extra></extra>")
        fig2 = apply_chart_theme(fig2, "Monthly Order Volume", height=350)
        fig2.update_xaxes(tickangle=45)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        no_data_msg()

# ── Category & State breakdown ─────────────────────────────────────────────
section_header("Category & Geographic Revenue Distribution", icon="🗺️")

cat_rev = (
    fitems[fitems["order_status"] != "canceled"]
    .groupby("category_english")["item_revenue"].sum()
    .nlargest(10).reset_index()
    .rename(columns={"category_english": "RawCategory", "item_revenue": "Revenue"})
)
cat_rev["Category"] = cat_rev["RawCategory"].apply(format_category_name)
cat_rev = cat_rev.sort_values("Revenue", ascending=True)

state_rev = (
    fom.groupby("customer_state")
    .agg(revenue=("product_revenue", "sum"), orders=("order_id", "nunique"))
    .reset_index()
    .sort_values("revenue", ascending=False)
    .head(15)
)

c1, c2 = st.columns(2)
with c1:
    if not cat_rev.empty:
        fig3 = px.bar(
            cat_rev,
            x="Revenue",
            y="Category",
            orientation="h",
            color_discrete_sequence=["#2563EB"],
            labels={"Revenue": "Revenue (R$)", "Category": "Product Category"},
        )
        fig3.update_traces(hovertemplate="<b>%{y}</b><br>Revenue: R$ %{x:,.2f}<extra></extra>")
        fig3 = apply_chart_theme(fig3, "Top 10 Product Categories by Revenue", height=390)
        fig3.update_layout(margin=dict(l=10, r=20, t=50, b=30))
        st.plotly_chart(fig3, use_container_width=True)
    else:
        no_data_msg()

with c2:
    if not state_rev.empty:
        fig4 = px.bar(
            state_rev,
            x="customer_state",
            y="revenue",
            color_discrete_sequence=["#0D9488"],
            labels={"customer_state": "Brazilian State Code", "revenue": "Revenue (R$)"},
        )
        fig4.update_traces(hovertemplate="<b>State %{x}</b><br>Revenue: R$ %{y:,.2f}<extra></extra>")
        fig4 = apply_chart_theme(fig4, "Revenue by Customer State (Top 15 States)", height=390)
        st.plotly_chart(fig4, use_container_width=True)
    else:
        no_data_msg()

# ── Product top 10 & Order status ─────────────────────────────────────────────
section_header("Product Performance & Order Status Integrity", icon="🏷️")

# Top products calculation with clean honest formatting
top_prod = (
    fitems[fitems["order_status"] != "canceled"]
    .groupby(["product_id", "category_english"])
    .agg(
        revenue=("item_revenue", "sum"),
        units=("item_revenue", "count"),
        avg_price=("price", "mean"),
    )
    .reset_index()
    .sort_values("revenue", ascending=False)
    .head(10)
)
top_prod["product_label"] = top_prod.apply(
    lambda r: format_product_label(r["product_id"], r["category_english"]), axis=1
)
top_prod = top_prod.sort_values("revenue", ascending=True)

# Order status distribution with percentages
status_dist = (
    fom.groupby("order_status")["order_id"].nunique().reset_index()
    .rename(columns={"order_id": "count"})
    .sort_values("count", ascending=False)
)
total_status_orders = status_dist["count"].sum()
status_dist["pct"] = (status_dist["count"] / total_status_orders * 100).round(2)
status_dist["status_display"] = status_dist["order_status"].str.capitalize()
status_dist = status_dist.sort_values("count", ascending=True)

c1, c2 = st.columns(2)
with c1:
    if not top_prod.empty:
        fig5 = px.bar(
            top_prod,
            x="revenue",
            y="product_label",
            orientation="h",
            color_discrete_sequence=["#2563EB"],
            labels={"revenue": "Revenue (R$)", "product_label": "Product & Category"},
        )
        fig5.update_traces(
            hovertemplate="<b>%{y}</b><br>Revenue: R$ %{x:,.2f}<extra></extra>"
        )
        fig5 = apply_chart_theme(fig5, "Top 10 Products by Revenue (with Category)", height=400)
        fig5.update_layout(margin=dict(l=10, r=20, t=50, b=30))
        st.plotly_chart(fig5, use_container_width=True)
    else:
        no_data_msg()

with c2:
    if not status_dist.empty:
        # High-contrast horizontal bar chart solves the 97.8% delivered overlapping label issue
        fig6 = px.bar(
            status_dist,
            x="count",
            y="status_display",
            orientation="h",
            text="count",
            color_discrete_sequence=["#0D9488"],
            labels={"count": "Orders", "status_display": "Order Status"},
        )
        fig6.update_traces(
            texttemplate="%{x:,}",
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Orders: %{x:,}<extra></extra>",
        )
        fig6 = apply_chart_theme(fig6, "Order Status Distribution (Non-Overlapping)", height=400)
        fig6.update_layout(margin=dict(l=10, r=50, t=50, b=30))
        st.plotly_chart(fig6, use_container_width=True)
    else:
        no_data_msg()

data_source_badge()
