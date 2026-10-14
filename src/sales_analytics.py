"""
Sales analytics for RetailScope.

Functions that compute sales KPIs and time-series aggregations
from precomputed Parquet tables.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def compute_kpis(order_metrics: DataFrame, status_filter: list[str] | None = None) -> dict:
    """
    Compute top-level sales KPIs.

    Args:
        order_metrics: Order-level metrics DataFrame.
        status_filter: If provided, only include these order statuses.

    Returns:
        Dict with KPI values.
    """
    df = order_metrics
    if status_filter:
        df = df.filter(F.col("order_status").isin(status_filter))

    row = df.agg(
        F.sum("product_revenue").alias("total_revenue"),
        F.countDistinct("order_id").alias("total_orders"),
        F.countDistinct("customer_unique_id").alias("total_customers"),
        F.avg("product_revenue").alias("avg_order_value"),
        F.avg("review_score").alias("avg_review_score"),
    ).collect()[0]

    total_customers = row["total_customers"] or 0

    # Repeat customer rate
    if total_customers > 0:
        repeat_df = (
            df.groupBy("customer_unique_id")
            .agg(F.countDistinct("order_id").alias("order_count"))
        )
        repeat_customers = repeat_df.filter(F.col("order_count") > 1).count()
        repeat_rate = round(repeat_customers / total_customers * 100, 2)
    else:
        repeat_customers = 0
        repeat_rate = 0.0

    return {
        "total_revenue": round(row["total_revenue"] or 0, 2),
        "total_orders": row["total_orders"] or 0,
        "total_customers": total_customers,
        "avg_order_value": round(row["avg_order_value"] or 0, 2),
        "avg_review_score": round(row["avg_review_score"] or 0, 2),
        "repeat_customers": repeat_customers,
        "repeat_rate": repeat_rate,
    }


def monthly_revenue(order_metrics: DataFrame) -> DataFrame:
    """Monthly revenue trend."""
    return (
        order_metrics
        .groupBy("purchase_year_month")
        .agg(
            F.sum("product_revenue").alias("revenue"),
            F.countDistinct("order_id").alias("orders"),
            F.avg("product_revenue").alias("avg_order_value"),
        )
        .orderBy("purchase_year_month")
    )


def daily_revenue(order_metrics: DataFrame) -> DataFrame:
    """Daily revenue trend."""
    return (
        order_metrics
        .groupBy("purchase_date")
        .agg(
            F.sum("product_revenue").alias("revenue"),
            F.countDistinct("order_id").alias("orders"),
        )
        .orderBy("purchase_date")
    )


def revenue_by_category(order_metrics: DataFrame, top_n: int = 10) -> DataFrame:
    """Revenue by product category."""
    return (
        order_metrics
        .filter(F.col("primary_category").isNotNull())
        .groupBy("primary_category")
        .agg(
            F.sum("product_revenue").alias("revenue"),
            F.countDistinct("order_id").alias("orders"),
        )
        .orderBy(F.col("revenue").desc())
        .limit(top_n)
    )


def revenue_by_state(order_metrics: DataFrame) -> DataFrame:
    """Revenue by customer state."""
    return (
        order_metrics
        .filter(F.col("customer_state").isNotNull())
        .groupBy("customer_state")
        .agg(
            F.sum("product_revenue").alias("revenue"),
            F.countDistinct("order_id").alias("orders"),
            F.countDistinct("customer_unique_id").alias("customers"),
        )
        .orderBy(F.col("revenue").desc())
    )


def order_status_distribution(order_metrics: DataFrame) -> DataFrame:
    """Count orders by status."""
    return (
        order_metrics
        .groupBy("order_status")
        .agg(F.countDistinct("order_id").alias("count"))
        .orderBy(F.col("count").desc())
    )


def weekday_pattern(order_metrics: DataFrame) -> DataFrame:
    """Orders and revenue by day of week (1=Sunday, 7=Saturday in Spark)."""
    day_labels = {
        1: "Sunday", 2: "Monday", 3: "Tuesday", 4: "Wednesday",
        5: "Thursday", 6: "Friday", 7: "Saturday",
    }
    mapping_expr = F.create_map([F.lit(x) for kv in day_labels.items() for x in kv])

    return (
        order_metrics
        .groupBy("purchase_day_of_week")
        .agg(
            F.sum("product_revenue").alias("revenue"),
            F.countDistinct("order_id").alias("orders"),
        )
        .withColumn("day_name", mapping_expr[F.col("purchase_day_of_week")])
        .orderBy("purchase_day_of_week")
    )


def hourly_pattern(order_metrics: DataFrame) -> DataFrame:
    """Orders by hour of day."""
    return (
        order_metrics
        .groupBy("purchase_hour")
        .agg(
            F.countDistinct("order_id").alias("orders"),
            F.sum("product_revenue").alias("revenue"),
        )
        .orderBy("purchase_hour")
    )
