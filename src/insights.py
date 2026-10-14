"""
Business insights engine for RetailScope.

Generates data-driven insights from computed analytical results.
Each insight includes: title, value, context, interpretation.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def _safe_collect_first(df: DataFrame, col: str):
    """Safely collect the first value of a column."""
    rows = df.collect()
    if rows:
        return rows[0][col]
    return None


def generate_insights(
    order_metrics: DataFrame,
    customer_rfm: DataFrame,
    item_data: DataFrame,
    payments: DataFrame,
) -> list[dict]:
    """
    Generate a list of business insights from the data.
    Each insight is a dict with: title, value, context, interpretation, category.
    """
    insights = []

    # --- 1. Highest revenue month ---
    try:
        monthly = (
            order_metrics
            .groupBy("purchase_year_month")
            .agg(F.sum("product_revenue").alias("revenue"))
            .orderBy(F.col("revenue").desc())
        )
        top_month = monthly.first()
        if top_month:
            insights.append({
                "title": "Highest Revenue Month",
                "value": f"R$ {top_month['revenue']:,.2f}",
                "context": f"Month: {top_month['purchase_year_month']}",
                "interpretation": "This was the peak revenue month in the dataset period.",
                "category": "Revenue",
            })
    except Exception:
        pass

    # --- 2. Top revenue category ---
    try:
        cat_rev = (
            item_data
            .filter(F.col("order_status") != "canceled")
            .groupBy("category_english")
            .agg(F.sum("item_revenue").alias("revenue"))
            .orderBy(F.col("revenue").desc())
        )
        total_rev = cat_rev.agg(F.sum("revenue")).collect()[0][0] or 1
        top_cat = cat_rev.first()
        if top_cat:
            share = round(top_cat["revenue"] / total_rev * 100, 1)
            cat_display = top_cat["category_english"].replace("_", " ").title()
            insights.append({
                "title": "Top Revenue Category",
                "value": cat_display,
                "context": f"R$ {top_cat['revenue']:,.2f} ({share}% of total)",
                "interpretation": f"This category contributed {share}% of all product revenue.",
                "category": "Products",
            })
    except Exception:
        pass

    # --- 3. Top 5 categories revenue share ---
    try:
        top5 = cat_rev.limit(5).agg(F.sum("revenue")).collect()[0][0] or 0
        top5_share = round(top5 / total_rev * 100, 1)
        insights.append({
            "title": "Top 5 Categories Revenue Share",
            "value": f"{top5_share}%",
            "context": f"R$ {top5:,.2f} out of R$ {total_rev:,.2f}",
            "interpretation": "Revenue concentration among the top product categories.",
            "category": "Products",
        })
    except Exception:
        pass

    # --- 4. State with highest order volume ---
    try:
        state_orders = (
            order_metrics
            .filter(F.col("customer_state").isNotNull())
            .groupBy("customer_state")
            .agg(F.countDistinct("order_id").alias("orders"))
            .orderBy(F.col("orders").desc())
        )
        top_state = state_orders.first()
        total_orders = state_orders.agg(F.sum("orders")).collect()[0][0] or 1
        if top_state:
            share = round(top_state["orders"] / total_orders * 100, 1)
            insights.append({
                "title": "Highest Order Volume State",
                "value": f"{top_state['customer_state']} — {top_state['orders']:,} orders",
                "context": f"{share}% of all orders",
                "interpretation": f"State {top_state['customer_state']} dominates order volume.",
                "category": "Geography",
            })
    except Exception:
        pass

    # --- 5. Repeat vs one-time customer comparison ---
    try:
        total_cust = customer_rfm.count()
        repeat = customer_rfm.filter(F.col("is_repeat") == True)
        repeat_count = repeat.count()
        repeat_rev = repeat.agg(F.sum("monetary")).collect()[0][0] or 0
        total_rev_cust = customer_rfm.agg(F.sum("monetary")).collect()[0][0] or 1
        rev_share = round(repeat_rev / total_rev_cust * 100, 1)
        cust_share = round(repeat_count / total_cust * 100, 1) if total_cust > 0 else 0

        insights.append({
            "title": "Repeat Customers Revenue Impact",
            "value": f"{cust_share}% of customers → {rev_share}% of revenue",
            "context": f"{repeat_count:,} repeat customers out of {total_cust:,} total",
            "interpretation": (
                "Repeat customers generate disproportionately more revenue. "
                "Investing in retention could significantly increase revenue."
                if rev_share > cust_share else
                "Repeat and one-time customers contribute similarly to revenue."
            ),
            "category": "Customers",
        })
    except Exception:
        pass

    # --- 6. Late delivery and review score relationship ---
    try:
        delivered = order_metrics.filter(
            (F.col("order_status") == "delivered")
            & F.col("delivery_delay_days").isNotNull()
            & F.col("review_score").isNotNull()
        )
        late = delivered.filter(F.col("is_late") == True)
        ontime = delivered.filter(F.col("is_late") == False)

        late_avg = late.agg(F.avg("review_score")).collect()[0][0]
        ontime_avg = ontime.agg(F.avg("review_score")).collect()[0][0]

        if late_avg is not None and ontime_avg is not None:
            diff = round(ontime_avg - late_avg, 2)
            insights.append({
                "title": "Late Delivery Impact on Reviews",
                "value": f"Δ {diff} stars",
                "context": (
                    f"On-time avg: {ontime_avg:.2f} ★ | "
                    f"Late avg: {late_avg:.2f} ★"
                ),
                "interpretation": (
                    "Late deliveries are associated with lower review scores. "
                    "Note: correlation does not necessarily establish causation — "
                    "other factors may also influence reviews."
                ),
                "category": "Operations",
            })
    except Exception:
        pass

    # --- 7. Champions segment opportunity ---
    try:
        champions = customer_rfm.filter(F.col("segment") == "Champions")
        champ_count = champions.count()
        champ_rev = champions.agg(F.sum("monetary")).collect()[0][0] or 0
        champ_pct = round(champ_count / total_cust * 100, 1) if total_cust > 0 else 0

        insights.append({
            "title": "Champions Segment",
            "value": f"{champ_count:,} customers ({champ_pct}%)",
            "context": f"Revenue contribution: R$ {champ_rev:,.2f}",
            "interpretation": (
                "Champions are your best customers — recent, frequent, high-spending. "
                "Focus on rewarding them and turning them into advocates."
            ),
            "category": "Customers",
        })
    except Exception:
        pass

    # --- 8. At Risk segment warning ---
    try:
        at_risk = customer_rfm.filter(F.col("segment") == "At Risk")
        risk_count = at_risk.count()
        risk_rev = at_risk.agg(F.sum("monetary")).collect()[0][0] or 0
        risk_pct = round(risk_count / total_cust * 100, 1) if total_cust > 0 else 0

        if risk_count > 0:
            insights.append({
                "title": "At Risk Customers",
                "value": f"{risk_count:,} customers ({risk_pct}%)",
                "context": f"Past revenue from this group: R$ {risk_rev:,.2f}",
                "interpretation": (
                    "These customers used to buy frequently but haven't ordered recently. "
                    "Consider win-back campaigns with special offers."
                ),
                "category": "Customers",
            })
    except Exception:
        pass

    # --- 9. Most popular payment method ---
    try:
        pay_dist = (
            payments
            .groupBy("payment_type")
            .agg(F.count("*").alias("count"))
            .orderBy(F.col("count").desc())
        )
        top_pay = pay_dist.first()
        total_pay = pay_dist.agg(F.sum("count")).collect()[0][0] or 1
        if top_pay:
            share = round(top_pay["count"] / total_pay * 100, 1)
            pay_display = top_pay["payment_type"].replace("_", " ").title()
            insights.append({
                "title": "Dominant Payment Method",
                "value": f"{pay_display} ({share}%)",
                "context": f"{top_pay['count']:,} out of {int(total_pay):,} transactions",
                "interpretation": f"{pay_display} is the dominant payment method in Brazilian e-commerce.",
                "category": "Payments",
            })
    except Exception:
        pass

    # --- 10. Weekend vs weekday comparison ---
    try:
        # Spark: dayofweek 1=Sunday, 7=Saturday
        weekend_rev = (
            order_metrics
            .filter(F.col("purchase_day_of_week").isin(1, 7))
            .agg(F.sum("product_revenue"))
            .collect()[0][0] or 0
        )
        weekday_rev = (
            order_metrics
            .filter(~F.col("purchase_day_of_week").isin(1, 7))
            .agg(F.sum("product_revenue"))
            .collect()[0][0] or 0
        )
        total_all = weekend_rev + weekday_rev
        if total_all > 0:
            wknd_pct = round(weekend_rev / total_all * 100, 1)
            insights.append({
                "title": "Weekend vs Weekday Revenue",
                "value": f"Weekday: {100 - wknd_pct}% | Weekend: {wknd_pct}%",
                "context": (
                    f"Weekday: R$ {weekday_rev:,.2f} | "
                    f"Weekend: R$ {weekend_rev:,.2f}"
                ),
                "interpretation": "Weekday purchasing dominates, consistent with B2C e-commerce patterns.",
                "category": "Trends",
            })
    except Exception:
        pass

    return insights
