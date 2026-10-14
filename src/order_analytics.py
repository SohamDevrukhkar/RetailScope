"""
Order, payment, and review analytics for RetailScope.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def delivery_stats(order_metrics: DataFrame) -> dict:
    """Compute delivery performance statistics."""
    delivered = order_metrics.filter(F.col("order_status") == "delivered")

    row = delivered.agg(
        F.avg("delivery_days").alias("avg_delivery_days"),
        F.avg("estimated_delivery_days").alias("avg_estimated_days"),
        F.avg("delivery_delay_days").alias("avg_delay_days"),
    ).collect()[0]

    total_delivered = delivered.filter(F.col("delivery_days").isNotNull()).count()
    late_count = delivered.filter(F.col("is_late") == True).count()
    late_pct = round(late_count / total_delivered * 100, 2) if total_delivered > 0 else 0

    return {
        "avg_delivery_days": round(row["avg_delivery_days"] or 0, 1),
        "avg_estimated_days": round(row["avg_estimated_days"] or 0, 1),
        "avg_delay_days": round(row["avg_delay_days"] or 0, 1),
        "late_delivery_count": late_count,
        "total_delivered": total_delivered,
        "late_delivery_pct": late_pct,
    }


def payment_distribution(payments: DataFrame) -> DataFrame:
    """Payment method distribution."""
    return (
        payments
        .groupBy("payment_type")
        .agg(
            F.count("*").alias("transaction_count"),
            F.sum("payment_value").alias("total_value"),
            F.avg("payment_value").alias("avg_value"),
        )
        .orderBy(F.col("transaction_count").desc())
    )


def installment_analysis(payments: DataFrame) -> DataFrame:
    """Analyze payment installment patterns."""
    return (
        payments
        .filter(F.col("payment_installments").isNotNull() & (F.col("payment_installments") > 0))
        .groupBy("payment_installments")
        .agg(
            F.count("*").alias("count"),
            F.avg("payment_value").alias("avg_value"),
            F.sum("payment_value").alias("total_value"),
        )
        .orderBy("payment_installments")
    )


def review_distribution(order_metrics: DataFrame) -> DataFrame:
    """Distribution of review scores."""
    return (
        order_metrics
        .filter(F.col("review_score").isNotNull())
        .groupBy("review_score")
        .agg(F.countDistinct("order_id").alias("count"))
        .orderBy("review_score")
    )


def delay_vs_review(order_metrics: DataFrame) -> DataFrame:
    """
    Relationship between delivery delay and review scores.
    Groups delays into buckets.
    """
    delivered = order_metrics.filter(
        (F.col("order_status") == "delivered")
        & F.col("delivery_delay_days").isNotNull()
        & F.col("review_score").isNotNull()
    )

    bucketed = delivered.withColumn(
        "delay_bucket",
        F.when(F.col("delivery_delay_days") <= -7, "7+ days early")
        .when(F.col("delivery_delay_days") <= -1, "1-6 days early")
        .when(F.col("delivery_delay_days") == 0, "On time")
        .when(F.col("delivery_delay_days") <= 7, "1-7 days late")
        .when(F.col("delivery_delay_days") <= 14, "8-14 days late")
        .otherwise("15+ days late"),
    )

    return (
        bucketed
        .groupBy("delay_bucket")
        .agg(
            F.avg("review_score").alias("avg_review_score"),
            F.count("*").alias("order_count"),
        )
        .orderBy("delay_bucket")
    )
