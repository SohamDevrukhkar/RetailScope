"""
Page 5 — Geographic Analytics
Territorial distribution of customers, sellers, orders, and revenue across Brazil.
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
    configure_page, render_page_header, get_spark, load_order_metrics, load_sellers,
    kpi_card, section_header, apply_chart_theme, no_data_msg,
    render_date_filters, filter_by_dates,
    pipeline_not_run_error, check_processed_data,
    data_source_badge, PLOTLY_COLORS,
)
from src.geographic_analytics import STATE_REGION, STATE_NAMES

configure_page("Geographic Analytics", "🗺️")

if not check_processed_data():
    pipeline_not_run_error()
    st.stop()

spark = get_spark()
om = load_order_metrics(spark)
sellers = load_sellers(spark)

om["purchase_date"] = pd.to_datetime(om["purchase_date"])

# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### 🔧 Geographic Controls")
start, end = render_date_filters(om)
fom = filter_by_dates(om, start, end)

render_page_header(
    title="Geographic Analytics",
    subtitle="Macro territorial distribution · Buyer concentration, merchant presence, and regional market penetration across Brazil",
    icon="🗺️",
    date_range=(start, end),
    badge_text="27 Brazilian Federative Units",
)

if fom.empty:
    no_data_msg()
    st.stop()

# ── State-level aggregation ──────────────────────────────────────────────────
state_agg = (
    fom.groupby("customer_state").agg(
        orders=("order_id", "nunique"),
        revenue=("product_revenue", "sum"),
        customers=("customer_unique_id", "nunique"),
    ).reset_index()
    .sort_values("revenue", ascending=False)
)
state_agg["region"] = state_agg["customer_state"].map(STATE_REGION).fillna("Other")
state_agg["state_name"] = state_agg["customer_state"].map(STATE_NAMES).fillna(state_agg["customer_state"])

# ── KPIs ─────────────────────────────────────────────────────────────────────
section_header("Territorial Coverage KPIs", icon="💎")
states_covered = state_agg["customer_state"].nunique()
top_state = state_agg.iloc[0] if not state_agg.empty else None

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Active Customer States", f"{states_covered} / 27", delta="Complete national coverage", color="#2563EB", icon="🇧🇷")
with k2:
    if top_state is not None:
        kpi_card("Top State by Revenue", f"{top_state['customer_state']} ({top_state.get('state_name','')})", delta=f"R$ {top_state['revenue']:,.0f} ({top_state['orders']:,} orders)", color="#0D9488", icon="🥇")
with k3:
    kpi_card("Active Seller States", f"{sellers['seller_state'].nunique()} / 27", delta=f"{sellers['seller_id'].nunique():,} total registered merchants", color="#F59E0B", icon="🏪")
with k4:
    reg_agg = state_agg.groupby("region")["revenue"].sum().sort_values(ascending=False)
    if not reg_agg.empty:
        reg_share = (reg_agg.iloc[0] / reg_agg.sum() * 100).round(1)
        kpi_card("Top Macro-Region", f"{reg_agg.index[0]}", delta=f"R$ {reg_agg.iloc[0]:,.0f} ({reg_share}% of revenue)", color="#8B5CF6", icon="🧭")

st.markdown("<br>", unsafe_allow_html=True)

# ── Revenue & orders by state ────────────────────────────────────────────────
section_header("State Revenue & Order Volumes (Top 15 States)", icon="📊")

c1, c2 = st.columns(2)
with c1:
    fig1 = px.bar(
        state_agg.head(15),
        x="customer_state",
        y="revenue",
        color="region",
        color_discrete_sequence=PLOTLY_COLORS,
        labels={"customer_state": "State Code", "revenue": "Revenue (R$)", "region": "Macro-Region"},
    )
    fig1.update_traces(
        hovertemplate="<b>State %{x}</b><br>Revenue: R$ %{y:,.2f}<extra></extra>"
    )
    fig1 = apply_chart_theme(fig1, "Product Revenue by Customer State (Top 15)", height=370)
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    fig2 = px.bar(
        state_agg.head(15),
        x="customer_state",
        y="orders",
        color="region",
        color_discrete_sequence=PLOTLY_COLORS,
        labels={"customer_state": "State Code", "orders": "Distinct Orders", "region": "Macro-Region"},
    )
    fig2.update_traces(
        hovertemplate="<b>State %{x}</b><br>Orders: %{y:,}<extra></extra>"
    )
    fig2 = apply_chart_theme(fig2, "Order Count by Customer State (Top 15)", height=370)
    st.plotly_chart(fig2, use_container_width=True)

# ── Customer distribution by state ───────────────────────────────────────────
section_header("Customer & Regional Share Dynamics", icon="👥")

c1, c2 = st.columns(2)
with c1:
    cust_top15 = state_agg.sort_values("customers", ascending=True).tail(15)
    fig3 = px.bar(
        cust_top15,
        x="customers",
        y="customer_state",
        orientation="h",
        color="region",
        color_discrete_sequence=PLOTLY_COLORS,
        labels={"customers": "Unique Customers", "customer_state": "State Code", "region": "Macro-Region"},
    )
    fig3.update_traces(
        hovertemplate="<b>State %{y}</b><br>Unique Customers: %{x:,}<extra></extra>"
    )
    fig3 = apply_chart_theme(fig3, "Unique Customers by State (Top 15)", height=380)
    fig3.update_layout(margin=dict(l=10, r=20, t=50, b=30))
    st.plotly_chart(fig3, use_container_width=True)

with c2:
    region_agg = state_agg.groupby("region").agg(
        revenue=("revenue", "sum"),
        orders=("orders", "sum"),
        customers=("customers", "sum"),
    ).reset_index().sort_values("revenue", ascending=False)

    fig4 = px.pie(
        region_agg,
        names="region",
        values="revenue",
        color="region",
        color_discrete_sequence=PLOTLY_COLORS,
        hole=0.45,
    )
    fig4.update_traces(
        textposition="inside",
        textinfo="percent",
        hovertemplate="<b>Region %{label}</b><br>Revenue: R$ %{value:,.2f}<br>Share: %{percent}<extra></extra>",
    )
    fig4 = apply_chart_theme(fig4, "Revenue Share by Brazilian Macro-Region", height=380)
    st.plotly_chart(fig4, use_container_width=True)

# ── Customer vs Seller comparison ────────────────────────────────────────────
section_header("Customer vs. Seller Geographic Concentration", icon="⚖️")

seller_state = (
    sellers.groupby("seller_state")
    .agg(seller_count=("seller_id", "nunique"))
    .reset_index()
    .sort_values("seller_count", ascending=False)
)
seller_state["region"] = seller_state["seller_state"].map(STATE_REGION)

cust_cnt = state_agg[["customer_state", "customers"]].rename(
    columns={"customer_state": "state", "customers": "Customers"}
)
sell_cnt = seller_state[["seller_state", "seller_count"]].rename(
    columns={"seller_state": "state", "seller_count": "Sellers"}
)

merged = pd.merge(cust_cnt, sell_cnt, on="state", how="outer").fillna(0)
merged = merged.sort_values("Customers", ascending=False).head(15)

fig7 = go.Figure()
fig7.add_trace(go.Bar(
    x=merged["state"],
    y=merged["Customers"],
    name="Buyers (Unique Customers)",
    marker_color="#2563EB",
    hovertemplate="<b>State %{x}</b><br>Buyers: %{y:,}<extra></extra>",
))
fig7.add_trace(go.Bar(
    x=merged["state"],
    y=merged["Sellers"],
    name="Merchants (Sellers)",
    marker_color="#EF4444",
    hovertemplate="<b>State %{x}</b><br>Sellers: %{y:,}<extra></extra>",
))
fig7 = apply_chart_theme(fig7, "Customer vs. Seller Footprint by State (Top 15 States)", height=370)
fig7.update_layout(barmode="group")
st.plotly_chart(fig7, use_container_width=True)

# ── State data table ──────────────────────────────────────────────────────────
section_header("Comprehensive 27 Federative Units Benchmark", icon="📋")
state_agg["rev_share"] = (state_agg["revenue"] / state_agg["revenue"].sum() * 100).round(2)
state_agg["aov"] = (state_agg["revenue"] / state_agg["orders"]).round(2)

st.dataframe(
    state_agg[[
        "customer_state", "state_name", "region", "revenue", "rev_share", "orders", "customers", "aov"
    ]].rename(columns={
        "customer_state": "State Code",
        "state_name": "State Name",
        "region": "Macro-Region",
        "revenue": "Revenue (R$)",
        "rev_share": "National Share (%)",
        "orders": "Orders Placed",
        "customers": "Unique Customers",
        "aov": "AOV (R$)",
    }).style.format({
        "Revenue (R$)": "R$ {:,.2f}",
        "National Share (%)": "{:.2f}%",
        "Orders Placed": "{:,}",
        "Unique Customers": "{:,}",
        "AOV (R$)": "R$ {:,.2f}",
    }),
    use_container_width=True,
    hide_index=True,
)

data_source_badge()
