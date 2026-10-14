"""
Page 4 — Product & Category Analytics
Catalog performance, category revenue contributions, and product-level economics.
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
import pandas as pd

from src.ui_utils import (
    configure_page, render_page_header, get_spark, load_item_data,
    kpi_card, section_header, apply_chart_theme, no_data_msg,
    format_category_name, format_product_label,
    render_date_filters, filter_by_dates,
    pipeline_not_run_error, check_processed_data,
    data_source_badge, PLOTLY_COLORS,
)

configure_page("Product Analytics", "🏷️")

if not check_processed_data():
    pipeline_not_run_error()
    st.stop()

spark = get_spark()
items = load_item_data(spark)
items["purchase_date"] = pd.to_datetime(items["purchase_date"])

# Filter out canceled orders for valid merchandise analytics
active = items[items["order_status"] != "canceled"].copy()

# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### 🔧 Product Controls")
start, end = render_date_filters(active)

all_cats = sorted(active["category_english"].dropna().unique())
all_cats_map = {c: format_category_name(c) for c in all_cats}
cat_filter = st.sidebar.multiselect(
    "Filter by Category",
    options=all_cats,
    format_func=lambda x: all_cats_map.get(x, x),
    placeholder="All categories",
)

top_n = st.sidebar.slider("Top N Products Display Limit", min_value=5, max_value=25, value=10, step=5)

fa = filter_by_dates(active, start, end)
if cat_filter:
    fa = fa[fa["category_english"].isin(cat_filter)]

render_page_header(
    title="Product & Category Analytics",
    subtitle="Catalog economics · Product volume, translated category contributions, price distribution, and SKU turnover",
    icon="🏷️",
    date_range=(start, end),
    badge_text="Translated English Taxonomy",
)

if fa.empty:
    no_data_msg()
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────────
section_header("Catalog Performance KPIs", icon="💎")

total_rev = fa["item_revenue"].sum()
total_units = len(fa)
unique_prods = fa["product_id"].nunique()
unique_cats = fa["category_english"].nunique()
avg_price = fa["price"].mean()

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    kpi_card("Total Product Revenue", f"R$ {total_rev:,.0f}", delta="Sum of item prices", color="#2563EB", icon="💰")
with k2:
    kpi_card("Total Units Sold", f"{total_units:,}", delta="Order item rows", color="#0D9488", icon="📦")
with k3:
    kpi_card("Active Products", f"{unique_prods:,}", delta="Distinct product IDs", color="#F59E0B", icon="🔍")
with k4:
    kpi_card("Categories Active", f"{unique_cats}", delta="Translated categories", color="#8B5CF6", icon="📚")
with k5:
    kpi_card("Average Item Price", f"R$ {avg_price:,.2f}", delta="per merchandise unit", color="#10B981", icon="🏷️")

st.markdown("<br>", unsafe_allow_html=True)

# ── Top products by revenue ──────────────────────────────────────────────────
section_header(f"Top {top_n} Products by Revenue", icon="🏆")

top_rev = (
    fa.groupby(["product_id", "category_english"]).agg(
        revenue=("item_revenue", "sum"),
        units=("item_revenue", "count"),
        avg_price=("price", "mean"),
    ).reset_index()
    .sort_values("revenue", ascending=False)
    .head(top_n)
)

top_rev["product_label"] = top_rev.apply(
    lambda r: format_product_label(r["product_id"], r["category_english"]), axis=1
)
top_rev["CategoryPretty"] = top_rev["category_english"].apply(format_category_name)
top_rev = top_rev.sort_values("revenue", ascending=True)

fig1 = px.bar(
    top_rev,
    x="revenue",
    y="product_label",
    orientation="h",
    color="CategoryPretty",
    color_discrete_sequence=PLOTLY_COLORS,
    labels={"revenue": "Revenue (R$)", "product_label": "Product", "CategoryPretty": "Category"},
)
fig1.update_traces(
    hovertemplate="<b>%{y}</b><br>Revenue: R$ %{x:,.2f}<extra></extra>"
)
fig1 = apply_chart_theme(fig1, f"Top {top_n} Products by Revenue (with Category)", height=410)
fig1.update_layout(margin=dict(l=10, r=20, t=50, b=30), showlegend=True)
st.plotly_chart(fig1, use_container_width=True)

# ── Top products by units & revenue by category ──────────────────────────────
section_header("Unit Volume & Category Revenue Breakdown", icon="📊")

c1, c2 = st.columns(2)
with c1:
    top_units = (
        fa.groupby(["product_id", "category_english"]).agg(
            units=("item_revenue", "count"),
            revenue=("item_revenue", "sum"),
            avg_price=("price", "mean"),
        ).reset_index()
        .sort_values("units", ascending=False)
        .head(top_n)
    )
    top_units["product_label"] = top_units.apply(
        lambda r: format_product_label(r["product_id"], r["category_english"]), axis=1
    )
    top_units = top_units.sort_values("units", ascending=True)

    fig2 = px.bar(
        top_units,
        x="units",
        y="product_label",
        orientation="h",
        color_discrete_sequence=["#0D9488"],
        labels={"units": "Units Sold", "product_label": "Product"},
    )
    fig2.update_traces(
        hovertemplate="<b>%{y}</b><br>Units Sold: %{x:,}<extra></extra>"
    )
    fig2 = apply_chart_theme(fig2, f"Top {top_n} Products by Units Sold", height=400)
    fig2.update_layout(margin=dict(l=10, r=20, t=50, b=30))
    st.plotly_chart(fig2, use_container_width=True)

with c2:
    cat_rev = (
        fa.groupby("category_english")["item_revenue"].sum()
        .reset_index()
        .sort_values("item_revenue", ascending=False)
        .head(15)
    )
    cat_rev["CategoryPretty"] = cat_rev["category_english"].apply(format_category_name)
    total_cat_rev = cat_rev["item_revenue"].sum()
    cat_rev["share"] = (cat_rev["item_revenue"] / total_cat_rev * 100).round(2)
    cat_rev = cat_rev.sort_values("item_revenue", ascending=True)

    fig3 = px.bar(
        cat_rev,
        x="item_revenue",
        y="CategoryPretty",
        orientation="h",
        color_discrete_sequence=["#2563EB"],
        labels={"item_revenue": "Revenue (R$)", "CategoryPretty": "Product Category"},
    )
    fig3.update_traces(
        hovertemplate="<b>%{y}</b><br>Revenue: R$ %{x:,.2f}<extra></extra>"
    )
    fig3 = apply_chart_theme(fig3, "Top 15 Categories by Revenue", height=400)
    fig3.update_layout(margin=dict(l=10, r=20, t=50, b=30))
    st.plotly_chart(fig3, use_container_width=True)

# ── Category revenue share table ──────────────────────────────────────────────
section_header("Category Revenue Contribution Matrix", icon="📋")
cat_summary = (
    fa.groupby("category_english").agg(
        revenue=("item_revenue", "sum"),
        units=("item_revenue", "count"),
        distinct_products=("product_id", "nunique"),
        avg_price=("price", "mean"),
    ).reset_index()
    .sort_values("revenue", ascending=False)
)
all_merch_rev = cat_summary["revenue"].sum()
cat_summary["share_pct"] = (cat_summary["revenue"] / all_merch_rev * 100).round(2)
cat_summary["Category"] = cat_summary["category_english"].apply(format_category_name)

st.dataframe(
    cat_summary[[
        "Category", "revenue", "share_pct", "units", "distinct_products", "avg_price"
    ]].rename(columns={
        "revenue": "Revenue (R$)",
        "share_pct": "Revenue Share (%)",
        "units": "Units Sold",
        "distinct_products": "Unique SKUs",
        "avg_price": "Avg Item Price (R$)",
    }).style.format({
        "Revenue (R$)": "R$ {:,.2f}",
        "Revenue Share (%)": "{:.2f}%",
        "Units Sold": "{:,}",
        "Unique SKUs": "{:,}",
        "Avg Item Price (R$)": "R$ {:,.2f}",
    }),
    use_container_width=True,
    hide_index=True,
)

# ── Category trend over time ─────────────────────────────────────────────────
section_header("Top Category Performance Trajectory", icon="📈")

top5_cats = (
    fa.groupby("category_english")["item_revenue"].sum()
    .nlargest(5).index.tolist()
)
trend_data = fa[fa["category_english"].isin(top5_cats)].copy()
trend_data["CategoryPretty"] = trend_data["category_english"].apply(format_category_name)

monthly_trend = (
    trend_data.groupby(["purchase_year_month", "CategoryPretty"])["item_revenue"]
    .sum().reset_index()
    .sort_values("purchase_year_month")
)

fig5 = px.line(
    monthly_trend,
    x="purchase_year_month",
    y="item_revenue",
    color="CategoryPretty",
    markers=True,
    color_discrete_sequence=PLOTLY_COLORS,
    labels={"item_revenue": "Revenue (R$)", "purchase_year_month": "Month", "CategoryPretty": "Category"},
)
fig5.update_traces(
    hovertemplate="<b>%{data.name} (%{x})</b><br>Revenue: R$ %{y:,.2f}<extra></extra>"
)
fig5 = apply_chart_theme(fig5, "Monthly Revenue Trajectory — Top 5 Categories", height=380)
fig5.update_xaxes(tickangle=45)
st.plotly_chart(fig5, use_container_width=True)

# ── Low-sales products ────────────────────────────────────────────────────────
section_header("Long-Tail Inventory (Products with ≤ 2 Units Sold)", icon="📦")

low = (
    fa.groupby(["product_id", "category_english"]).agg(
        units=("item_revenue", "count"),
        revenue=("item_revenue", "sum"),
        avg_price=("price", "mean"),
    ).reset_index()
    .query("units <= 2")
    .sort_values("units")
)
low["Category"] = low["category_english"].apply(format_category_name)
low["ProductLabel"] = low.apply(lambda r: format_product_label(r["product_id"], r["category_english"]), axis=1)

st.markdown(
    f"In the selected period, **{len(low):,}** products sold 2 or fewer units, representing long-tail merchandise inventory."
)
st.dataframe(
    low[[
        "ProductLabel", "Category", "units", "revenue", "avg_price", "product_id"
    ]].head(100)
    .rename(columns={
        "ProductLabel": "Product Reference",
        "units": "Units Sold",
        "revenue": "Total Revenue (R$)",
        "avg_price": "Unit Price (R$)",
        "product_id": "Full Product UUID",
    }).style.format({
        "Total Revenue (R$)": "R$ {:,.2f}",
        "Unit Price (R$)": "R$ {:,.2f}",
        "Units Sold": "{:,}",
    }),
    use_container_width=True,
    hide_index=True,
)

data_source_badge()
