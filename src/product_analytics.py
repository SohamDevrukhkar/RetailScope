"""
Product and category analytics for RetailScope.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def top_products_by_revenue(item_data: DataFrame, n: int = 20) -> DataFrame:
    """Top N products by revenue."""
    return (
        item_data
        .filter(F.col("order_status") != "canceled")
        .groupBy("product_id", "category_english")
        .agg(
            F.sum("item_revenue").alias("revenue"),
            F.sum(F.lit(1)).alias("units_sold"),
            F.avg("price").alias("avg_price"),
        )
        .orderBy(F.col("revenue").desc())
        .limit(n)
    )


def top_products_by_units(item_data: DataFrame, n: int = 20) -> DataFrame:
    """Top N products by units sold."""
    return (
        item_data
        .filter(F.col("order_status") != "canceled")
        .groupBy("product_id", "category_english")
        .agg(
            F.sum(F.lit(1)).alias("units_sold"),
            F.sum("item_revenue").alias("revenue"),
        )
        .orderBy(F.col("units_sold").desc())
        .limit(n)
    )


def revenue_by_category(item_data: DataFrame, n: int = 20) -> DataFrame:
    """Revenue by product category with share calculation."""
    cat_rev = (
        item_data
        .filter(F.col("order_status") != "canceled")
        .groupBy("category_english")
        .agg(
            F.sum("item_revenue").alias("revenue"),
            F.sum(F.lit(1)).alias("units_sold"),
            F.countDistinct("product_id").alias("distinct_products"),
            F.avg("price").alias("avg_price"),
        )
        .orderBy(F.col("revenue").desc())
    )

    total_rev = cat_rev.agg(F.sum("revenue")).collect()[0][0] or 1
    cat_rev = cat_rev.withColumn(
        "revenue_share_pct",
        F.round(F.col("revenue") / F.lit(total_rev) * 100, 2),
    )

    return cat_rev.limit(n)


def category_trend(item_data: DataFrame) -> DataFrame:
    """Monthly revenue by top categories."""
    return (
        item_data
        .filter(F.col("order_status") != "canceled")
        .groupBy("purchase_year_month", "category_english")
        .agg(F.sum("item_revenue").alias("revenue"))
        .orderBy("purchase_year_month")
    )


def avg_price_by_category(item_data: DataFrame) -> DataFrame:
    """Average price by category."""
    return (
        item_data
        .filter(F.col("order_status") != "canceled")
        .groupBy("category_english")
        .agg(
            F.avg("price").alias("avg_price"),
            F.count("*").alias("items_sold"),
        )
        .orderBy(F.col("avg_price").desc())
    )


def low_sales_products(item_data: DataFrame, threshold: int = 2) -> DataFrame:
    """Products with very few sales (units sold <= threshold)."""
    return (
        item_data
        .filter(F.col("order_status") != "canceled")
        .groupBy("product_id", "category_english")
        .agg(
            F.sum(F.lit(1)).alias("units_sold"),
            F.sum("item_revenue").alias("revenue"),
        )
        .filter(F.col("units_sold") <= threshold)
        .orderBy(F.col("units_sold").asc())
    )
