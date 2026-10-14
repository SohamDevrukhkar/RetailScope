"""
Page 6 — Orders, Payments & Reviews
Logistical performance, fulfillment integrity, payment method economics, and customer satisfaction.
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
    configure_page, render_page_header, get_spark, load_order_metrics, load_payments,
    kpi_card, section_header, apply_chart_theme, no_data_msg,
    render_date_filters, filter_by_dates,
    pipeline_not_run_error, check_processed_data,
    data_source_badge, PLOTLY_COLORS,
)

configure_page("Orders, Payments & Reviews", "🛒")

if not check_processed_data():
    pipeline_not_run_error()
    st.stop()

spark = get_spark()
om = load_order_metrics(spark)
payments = load_payments(spark)

om["purchase_date"] = pd.to_datetime(om["purchase_date"])

# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### 🔧 Operational Controls")
start, end = render_date_filters(om)
fom = filter_by_dates(om, start, end)

render_page_header(
    title="Orders, Payments & Reviews",
    subtitle="Operations & Satisfaction · Logistics velocity, delivery delays, financial settlement methods, and review distributions",
    icon="🛒",
    date_range=(start, end),
    badge_text="Audited Order Records",
)

if fom.empty:
    no_data_msg()
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# ORDER STATUS INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════
section_header("Fulfillment Pipeline & Order Status Integrity", icon="📦")

status_dist = (
    fom.groupby("order_status")["order_id"].nunique()
    .reset_index().rename(columns={"order_id": "count"})
    .sort_values("count", ascending=True)
)
total_orders_scope = status_dist["count"].sum()
status_dist["pct"] = (status_dist["count"] / total_orders_scope * 100).round(2)
status_dist["status_display"] = status_dist["order_status"].str.capitalize()

c1, c2 = st.columns([3, 2])
with c1:
    tab_bar, tab_donut = st.tabs(["📊 Clear Horizontal Distribution", "🍩 High-Contrast Donut"])
    with tab_bar:
        # Non-overlapping horizontal bar chart perfectly solves the 97.8% delivered issue
        fig1 = px.bar(
            status_dist,
            x="count",
            y="status_display",
            orientation="h",
            color_discrete_sequence=["#2563EB"],
            labels={"count": "Orders", "status_display": "Status"},
        )
        fig1.update_traces(
            texttemplate="%{x:,} (%{customdata[0]}%)",
            textposition="outside",
            customdata=status_dist[["pct"]],
            hovertemplate="<b>%{y}</b><br>Orders: %{x:,}<br>Share: %{customdata[0]}%<extra></extra>",
        )
        fig1 = apply_chart_theme(fig1, "Order Volume & Share by Status", height=320)
        fig1.update_layout(margin=dict(l=10, r=80, t=40, b=30))
        st.plotly_chart(fig1, use_container_width=True)

    with tab_donut:
        fig1_donut = px.pie(
            status_dist.sort_values("count", ascending=False),
            names="status_display",
            values="count",
            color_discrete_sequence=PLOTLY_COLORS,
            hole=0.5,
        )
        fig1_donut.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>Orders: %{value:,}<br>Share: %{percent}<extra></extra>",
        )
        fig1_donut = apply_chart_theme(fig1_donut, "Order Status Donut (Inside Labels)", height=320)
        st.plotly_chart(fig1_donut, use_container_width=True)

with c2:
    st.markdown("**Order Status Audit Table**")
    st.dataframe(
        status_dist.sort_values("count", ascending=False)[[
            "status_display", "count", "pct"
        ]].rename(columns={
            "status_display": "Status Category",
            "count": "Order Count",
            "pct": "Share of Total (%)",
        }).style.format({
            "Order Count": "{:,}",
            "Share of Total (%)": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# DELIVERY PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
section_header("Logistical Transit & Delivery Lead Times", icon="🚚")

delivered = fom[fom["order_status"] == "delivered"].copy()
has_delivery = delivered.dropna(subset=["delivery_days"]).copy()

avg_del = has_delivery["delivery_days"].mean() if not has_delivery.empty else 0
avg_est = has_delivery["estimated_delivery_days"].mean() if not has_delivery.empty else 0
avg_delay = has_delivery["delivery_delay_days"].mean() if not has_delivery.empty else 0
late = has_delivery[has_delivery["is_late"] == True]
late_pct = (len(late) / len(has_delivery) * 100) if len(has_delivery) > 0 else 0

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Avg Actual Delivery", f"{avg_del:.1f} days", delta="Purchase to customer door", color="#2563EB", icon="⏱️")
with k2:
    kpi_card("Avg Estimated Delivery", f"{avg_est:.1f} days", delta="Estimated carrier promise", color="#0D9488", icon="📅")
with k3:
    sign = "+" if avg_delay > 0 else ""
    delta_note = "Early arrival on average" if avg_delay < 0 else "Average lag"
    kpi_card("Delivery Variance", f"{sign}{avg_delay:.1f} days", delta=delta_note, color="#F59E0B", icon="🎯")
with k4:
    kpi_card("Late Delivery Rate", f"{late_pct:.1f}%", delta=f"{len(late):,} late of {len(has_delivery):,} delivered", color="#EF4444", icon="⚠️")

st.markdown("<br>", unsafe_allow_html=True)

# Transit Time Histograms
c1, c2 = st.columns(2)
with c1:
    fig2 = px.histogram(
        has_delivery,
        x="delivery_days",
        nbins=40,
        color_discrete_sequence=["#2563EB"],
        labels={"delivery_days": "Actual Transit Time (Days)", "count": "Orders"},
    )
    fig2.update_traces(hovertemplate="Transit Time: %{x} days<br>Orders: %{y:,}<extra></extra>")
    fig2 = apply_chart_theme(fig2, "Transit Duration Distribution", height=340)
    fig2.add_vline(
        x=avg_del, line_dash="dash", line_color="#EF4444",
        annotation_text=f"Mean: {avg_del:.1f}d", annotation_position="top right"
    )
    st.plotly_chart(fig2, use_container_width=True)

with c2:
    delay_data = has_delivery["delivery_delay_days"].dropna()
    fig3 = px.histogram(
        delay_data,
        nbins=50,
        color_discrete_sequence=["#0D9488"],
        labels={"value": "Variance vs. Estimate (Days)", "count": "Orders"},
    )
    fig3.update_traces(hovertemplate="Delay: %{x} days<br>Orders: %{y:,}<extra></extra>")
    fig3 = apply_chart_theme(fig3, "Delivery Variance vs. Promised Date (Negative = Early)", height=340)
    fig3.add_vline(x=0, line_dash="solid", line_color="#EF4444", annotation_text="Promised Date")
    st.plotly_chart(fig3, use_container_width=True)

# Monthly late delivery rate
has_monthly = has_delivery.copy()
has_monthly["Month"] = has_monthly["purchase_date"].dt.strftime("%Y-%m")
month_late = (
    has_monthly.groupby("Month")["is_late"]
    .apply(lambda s: (s.sum() / len(s) * 100) if len(s) > 0 else 0)
    .reset_index(name="late_pct")
    .sort_values("Month")
)

fig4 = px.line(
    month_late,
    x="Month",
    y="late_pct",
    markers=True,
    color_discrete_sequence=["#EF4444"],
    labels={"late_pct": "Late Delivery Percentage (%)", "Month": "Month"},
)
fig4.update_traces(hovertemplate="<b>%{x}</b><br>Late Delivery Rate: %{y:.2f}%<extra></extra>")
fig4 = apply_chart_theme(fig4, "Monthly Late Delivery Incident Rate (%)", height=320)
fig4.update_xaxes(tickangle=45)
st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT METHODS & FINANCING
# ══════════════════════════════════════════════════════════════════════════════
section_header("Payment Methods & Installment Structures", icon="💳")

pay_dist = (
    payments.groupby("payment_type").agg(
        count=("payment_value", "count"),
        total=("payment_value", "sum"),
        avg=("payment_value", "mean"),
    ).reset_index().sort_values("count", ascending=False)
)
pay_dist["MethodPretty"] = pay_dist["payment_type"].str.replace("_", " ").str.title()

c1, c2 = st.columns(2)
with c1:
    fig5 = px.bar(
        pay_dist.sort_values("count", ascending=True),
        x="count",
        y="MethodPretty",
        orientation="h",
        color_discrete_sequence=["#2563EB"],
        labels={"count": "Transaction Count", "MethodPretty": "Payment Method"},
    )
    fig5.update_traces(hovertemplate="<b>%{y}</b><br>Transactions: %{x:,}<extra></extra>")
    fig5 = apply_chart_theme(fig5, "Transactions by Payment Method", height=340)
    fig5.update_layout(margin=dict(l=10, r=20, t=50, b=30))
    st.plotly_chart(fig5, use_container_width=True)

with c2:
    fig6 = px.bar(
        pay_dist.sort_values("total", ascending=True),
        x="total",
        y="MethodPretty",
        orientation="h",
        color_discrete_sequence=["#0D9488"],
        labels={"total": "Total Settled Value (R$)", "MethodPretty": "Payment Method"},
    )
    fig6.update_traces(hovertemplate="<b>%{y}</b><br>Value: R$ %{x:,.2f}<extra></extra>")
    fig6 = apply_chart_theme(fig6, "Total Settled Value by Payment Method", height=340)
    fig6.update_layout(margin=dict(l=10, r=20, t=50, b=30))
    st.plotly_chart(fig6, use_container_width=True)

# Installments
installments = (
    payments[payments["payment_installments"].notna() & (payments["payment_installments"] > 0)]
    .groupby("payment_installments").agg(
        count=("payment_value", "count"),
        avg_value=("payment_value", "mean"),
    ).reset_index()
    .sort_values("payment_installments")
    .head(18)
)

c1, c2 = st.columns(2)
with c1:
    fig7 = px.bar(
        installments,
        x="payment_installments",
        y="count",
        color_discrete_sequence=["#8B5CF6"],
        labels={"payment_installments": "Installment Count", "count": "Transactions"},
    )
    fig7.update_traces(hovertemplate="<b>%{x} Installments</b><br>Transactions: %{y:,}<extra></extra>")
    fig7 = apply_chart_theme(fig7, "Financing: Transactions by Installment Count", height=340)
    fig7.update_xaxes(dtick=1)
    st.plotly_chart(fig7, use_container_width=True)

with c2:
    fig8 = px.line(
        installments,
        x="payment_installments",
        y="avg_value",
        markers=True,
        color_discrete_sequence=["#F59E0B"],
        labels={"payment_installments": "Installment Count", "avg_value": "Avg Transaction Value (R$)"},
    )
    fig8.update_traces(hovertemplate="<b>%{x} Installments</b><br>Average Value: R$ %{y:,.2f}<extra></extra>")
    fig8 = apply_chart_theme(fig8, "Average Ticket Size vs. Installment Count", height=340)
    fig8.update_xaxes(dtick=1)
    st.plotly_chart(fig8, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER SATISFACTION (REVIEWS)
# ══════════════════════════════════════════════════════════════════════════════
section_header("Customer Satisfaction & Review Scores", icon="⭐")

review_data = fom.dropna(subset=["review_score"]).copy()
avg_score = review_data["review_score"].mean() if not review_data.empty else 0.0
total_reviews = len(review_data)

k1, k2 = st.columns([1, 3])
with k1:
    kpi_card("Overall Satisfaction", f"{avg_score:.2f} ★", delta=f"{total_reviews:,} total customer ratings", color="#F59E0B", icon="🌟")

with k2:
    score_dist = review_data.groupby("review_score")["order_id"].nunique().reset_index()
    score_dist.columns = ["score", "count"]
    score_dist["score_label"] = score_dist["score"].astype(int).apply(lambda s: f"{'★' * s} ({s})")

    color_map = {1: "#EF4444", 2: "#F97316", 3: "#F59E0B", 4: "#3B82F6", 5: "#10B981"}
    score_dist["color"] = score_dist["score"].map(color_map)

    fig9 = px.bar(
        score_dist,
        x="score_label",
        y="count",
        color="score",
        color_discrete_map=color_map,
        labels={"score_label": "Review Rating", "count": "Orders"},
    )
    fig9.update_traces(hovertemplate="<b>%{x}</b><br>Orders: %{y:,}<extra></extra>")
    fig9 = apply_chart_theme(fig9, "Review Rating Distribution (1–5 Stars)", height=320)
    fig9.update_layout(showlegend=False)
    st.plotly_chart(fig9, use_container_width=True)

# Relationship: Delivery delay vs review score
section_header("Impact of Delivery Timing on Review Scores", icon="🔬")

st.info(
    "⚠️ **Analytical Note:** A strong statistical correlation between delivery delays and lower review ratings is observed; "
    "however, correlation does not necessarily establish sole causation. Other unmeasured factors — such as product quality, "
    "carrier damage, and seller responsiveness — may also influence satisfaction."
)

delay_review = has_delivery.dropna(subset=["delivery_delay_days", "review_score"]).copy()
if not delay_review.empty:
    delay_review["delay_bucket"] = pd.cut(
        delay_review["delivery_delay_days"],
        bins=[-999, -7, -1, 0, 7, 14, 999],
        labels=[
            "7+ days early", "1-6 days early", "On time (0d)",
            "1-7 days late", "8-14 days late", "15+ days late",
        ],
    )
    bucket_avg = (
        delay_review.groupby("delay_bucket", observed=True)
        .agg(avg_score=("review_score", "mean"), count=("order_id", "nunique"))
        .reset_index()
    )

    fig10 = px.bar(
        bucket_avg,
        x="delay_bucket",
        y="avg_score",
        color="avg_score",
        color_continuous_scale=["#EF4444", "#F59E0B", "#10B981"],
        labels={"delay_bucket": "Delivery Timing Relative to Promise", "avg_score": "Average Star Rating"},
        text="avg_score",
    )
    fig10.update_traces(
        texttemplate="%{y:.2f} ★",
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Avg Score: %{y:.2f} ★<br>Sample Size: %{customdata[0]:,} orders<extra></extra>",
        customdata=bucket_avg[["count"]],
    )
    fig10 = apply_chart_theme(fig10, "Average Customer Rating by Fulfillment Timing", height=380)
    fig10.update_layout(coloraxis_showscale=False, yaxis=dict(range=[0, 5.3]))
    st.plotly_chart(fig10, use_container_width=True)
else:
    st.warning("Insufficient delivery timing data to compute review correlation.")

data_source_badge()
