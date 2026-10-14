"""
Customer segmentation analytics for RetailScope.

Reads precomputed RFM data and provides segment analysis functions.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


# Segment descriptions for display in the app
SEGMENT_DESCRIPTIONS = {
    "Champions": "Recent buyers, buy often, spend the most. Reward them and make them brand ambassadors.",
    "Loyal Customers": "Buy regularly with above-average frequency and spending. Upsell premium products.",
    "Potential Loyalists": "Recent mid-frequency buyers. Offer loyalty programs and recommendations.",
    "Recent Customers": "Bought recently but not frequently. Onboard them with targeted engagement.",
    "At Risk": "Used to buy often but haven't purchased recently. Re-engage with win-back campaigns.",
    "Lost": "Lowest recency and frequency. Attempt re-activation or deprioritize.",
    "Others": "Moderate engagement across dimensions. Nurture with general campaigns.",
}

RFM_SCORING_EXPLANATION = """
**RFM Scoring Method:**
- **Recency (R):** Days since the customer's last purchase. Lower is better. Scored 1–5 using quintiles (5 = most recent).
- **Frequency (F):** Number of distinct orders placed. Higher is better. Scored 1–5 using quintiles (5 = most orders).
- **Monetary (M):** Total product revenue from the customer. Higher is better. Scored 1–5 using quintiles (5 = highest spending).
- **Reference date:** One day after the last order in the dataset.
- **Customer identity:** Uses `customer_unique_id` to track customers across multiple `customer_id` records.
"""


def segment_distribution(rfm: DataFrame) -> DataFrame:
    """Count and revenue by customer segment."""
    return (
        rfm
        .groupBy("segment")
        .agg(
            F.count("*").alias("customer_count"),
            F.sum("monetary").alias("total_revenue"),
            F.avg("monetary").alias("avg_revenue"),
            F.avg("recency").alias("avg_recency"),
            F.avg("frequency").alias("avg_frequency"),
        )
        .orderBy(F.col("customer_count").desc())
    )


def top_customers(rfm: DataFrame, n: int = 20) -> DataFrame:
    """Top N customers by total spending."""
    return (
        rfm
        .select(
            "customer_unique_id", "monetary", "frequency",
            "recency", "segment", "customer_state",
            "first_purchase_date", "last_purchase_date",
            "avg_review_score",
        )
        .orderBy(F.col("monetary").desc())
        .limit(n)
    )


def repeat_vs_onetime(rfm: DataFrame) -> dict:
    """Compare repeat vs one-time customers."""
    repeat = rfm.filter(F.col("is_repeat") == True)
    onetime = rfm.filter(F.col("is_repeat") == False)

    total = rfm.count()
    repeat_count = repeat.count()
    onetime_count = onetime.count()

    repeat_rev = repeat.agg(F.sum("monetary")).collect()[0][0] or 0
    onetime_rev = onetime.agg(F.sum("monetary")).collect()[0][0] or 0

    return {
        "total_customers": total,
        "repeat_count": repeat_count,
        "onetime_count": onetime_count,
        "repeat_rate": round(repeat_count / total * 100, 2) if total > 0 else 0,
        "repeat_revenue": round(repeat_rev, 2),
        "onetime_revenue": round(onetime_rev, 2),
        "repeat_avg_spend": round(repeat_rev / repeat_count, 2) if repeat_count > 0 else 0,
        "onetime_avg_spend": round(onetime_rev / onetime_count, 2) if onetime_count > 0 else 0,
    }


def rfm_score_distribution(rfm: DataFrame) -> DataFrame:
    """Distribution of R, F, M scores."""
    r_dist = rfm.groupBy("r_score").count().withColumnRenamed("count", "r_count")
    f_dist = rfm.groupBy("f_score").count().withColumnRenamed("count", "f_count")
    m_dist = rfm.groupBy("m_score").count().withColumnRenamed("count", "m_count")
    return r_dist, f_dist, m_dist
