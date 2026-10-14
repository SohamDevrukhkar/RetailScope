"""
Data cleaning module for RetailScope.

Validates, cleans, and documents data quality issues across all datasets.
Returns cleaning reports alongside cleaned DataFrames.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import TimestampType


def _parse_timestamps(df: DataFrame, columns: list[str]) -> DataFrame:
    """Cast string timestamp columns to TimestampType."""
    for col in columns:
        if col in df.columns:
            df = df.withColumn(col, F.to_timestamp(F.col(col), "yyyy-MM-dd HH:mm:ss"))
    return df


def _count_issues(df: DataFrame, col: str) -> int:
    """Count null or empty values in a column."""
    return df.filter(F.col(col).isNull() | (F.trim(F.col(col)) == "")).count()


# ---------------------------------------------------------------------------
# Quality report
# ---------------------------------------------------------------------------

def run_quality_checks(datasets: dict) -> dict:
    """
    Run data quality checks on all raw datasets.
    Returns a dict with quality info per dataset.
    """
    report = {}

    for name, df in datasets.items():
        total = df.count()
        nulls = {}
        for c in df.columns:
            null_count = df.filter(F.col(c).isNull()).count()
            if null_count > 0:
                nulls[c] = null_count
        duplicates = total - df.dropDuplicates().count()

        entry = {
            "total_records": total,
            "columns": df.columns,
            "null_counts": nulls,
            "duplicate_records": duplicates,
        }
        report[name] = entry

    # Specific checks for orders
    if "orders" in datasets:
        orders = datasets["orders"]
        entry = report["orders"]
        entry["cancelled_orders"] = orders.filter(F.col("order_status") == "canceled").count()
        entry["unavailable_orders"] = orders.filter(F.col("order_status") == "unavailable").count()

    # Check for invalid prices in order_items
    if "order_items" in datasets:
        items = datasets["order_items"]
        entry = report["order_items"]
        entry["negative_prices"] = items.filter(F.col("price") < 0).count()
        entry["zero_prices"] = items.filter(F.col("price") == 0).count()
        entry["negative_freight"] = items.filter(F.col("freight_value") < 0).count()

    # Check reviews
    if "reviews" in datasets:
        reviews = datasets["reviews"]
        entry = report["reviews"]
        entry["invalid_scores"] = reviews.filter(
            (F.col("review_score") < 1) | (F.col("review_score") > 5)
        ).count()

    return report


# ---------------------------------------------------------------------------
# Cleaning functions
# ---------------------------------------------------------------------------

def clean_orders(df: DataFrame) -> tuple[DataFrame, dict]:
    """Clean orders dataset. Returns (cleaned_df, cleaning_log)."""
    log = {"original_count": df.count(), "steps": []}

    # Parse timestamps
    ts_cols = [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    df = _parse_timestamps(df, ts_cols)

    # Remove rows with null order_id or customer_id
    before = df.count()
    df = df.filter(F.col("order_id").isNotNull() & F.col("customer_id").isNotNull())
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with null order_id/customer_id")

    # Remove rows with null purchase timestamp
    before = df.count()
    df = df.filter(F.col("order_purchase_timestamp").isNotNull())
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with null purchase timestamp")

    # Remove exact duplicates
    before = df.count()
    df = df.dropDuplicates(["order_id"])
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} duplicate order_id rows")

    # Standardize order_status to lowercase
    df = df.withColumn("order_status", F.lower(F.trim(F.col("order_status"))))

    log["final_count"] = df.count()
    log["removed_total"] = log["original_count"] - log["final_count"]
    return df, log


def clean_order_items(df: DataFrame) -> tuple[DataFrame, dict]:
    """Clean order items dataset."""
    log = {"original_count": df.count(), "steps": []}

    df = _parse_timestamps(df, ["shipping_limit_date"])

    # Remove nulls in key columns
    before = df.count()
    df = df.filter(
        F.col("order_id").isNotNull()
        & F.col("product_id").isNotNull()
        & F.col("price").isNotNull()
    )
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with null order_id/product_id/price")

    # Remove negative prices (but keep zero; some are valid free items or bundles)
    before = df.count()
    df = df.filter(F.col("price") >= 0)
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with negative prices")

    # Fill null freight with 0
    df = df.fillna({"freight_value": 0.0})

    # Remove duplicates on composite key
    before = df.count()
    df = df.dropDuplicates(["order_id", "order_item_id"])
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} duplicate order+item rows")

    log["final_count"] = df.count()
    log["removed_total"] = log["original_count"] - log["final_count"]
    return df, log


def clean_customers(df: DataFrame) -> tuple[DataFrame, dict]:
    """Clean customers dataset."""
    log = {"original_count": df.count(), "steps": []}

    before = df.count()
    df = df.filter(F.col("customer_id").isNotNull() & F.col("customer_unique_id").isNotNull())
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with null IDs")

    before = df.count()
    df = df.dropDuplicates(["customer_id"])
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} duplicate customer_id rows")

    # Standardize state to uppercase
    df = df.withColumn("customer_state", F.upper(F.trim(F.col("customer_state"))))

    log["final_count"] = df.count()
    log["removed_total"] = log["original_count"] - log["final_count"]
    return df, log


def clean_products(df: DataFrame) -> tuple[DataFrame, dict]:
    """Clean products dataset."""
    log = {"original_count": df.count(), "steps": []}

    before = df.count()
    df = df.filter(F.col("product_id").isNotNull())
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with null product_id")

    before = df.count()
    df = df.dropDuplicates(["product_id"])
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} duplicate product_id rows")

    log["final_count"] = df.count()
    log["removed_total"] = log["original_count"] - log["final_count"]
    return df, log


def clean_payments(df: DataFrame) -> tuple[DataFrame, dict]:
    """Clean payments dataset."""
    log = {"original_count": df.count(), "steps": []}

    before = df.count()
    df = df.filter(F.col("order_id").isNotNull() & F.col("payment_value").isNotNull())
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with null order_id/payment_value")

    # Remove negative payment values
    before = df.count()
    df = df.filter(F.col("payment_value") >= 0)
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with negative payment_value")

    df = df.withColumn("payment_type", F.lower(F.trim(F.col("payment_type"))))

    log["final_count"] = df.count()
    log["removed_total"] = log["original_count"] - log["final_count"]
    return df, log


def clean_reviews(df: DataFrame) -> tuple[DataFrame, dict]:
    """Clean reviews dataset."""
    log = {"original_count": df.count(), "steps": []}

    df = _parse_timestamps(df, ["review_creation_date", "review_answer_timestamp"])

    before = df.count()
    df = df.filter(F.col("order_id").isNotNull() & F.col("review_score").isNotNull())
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} rows with null order_id/score")

    # Clamp scores to [1, 5]
    before_invalid = df.filter((F.col("review_score") < 1) | (F.col("review_score") > 5)).count()
    df = df.filter((F.col("review_score") >= 1) & (F.col("review_score") <= 5))
    if before_invalid:
        log["steps"].append(f"Removed {before_invalid} rows with invalid review scores")

    # Keep one review per order (latest)
    from pyspark.sql.window import Window
    w = Window.partitionBy("order_id").orderBy(F.col("review_creation_date").desc())
    df = df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")

    log["final_count"] = df.count()
    log["removed_total"] = log["original_count"] - log["final_count"]
    return df, log


def clean_sellers(df: DataFrame) -> tuple[DataFrame, dict]:
    """Clean sellers dataset."""
    log = {"original_count": df.count(), "steps": []}

    before = df.count()
    df = df.filter(F.col("seller_id").isNotNull())
    df = df.dropDuplicates(["seller_id"])
    removed = before - df.count()
    if removed:
        log["steps"].append(f"Removed {removed} null/duplicate seller rows")

    df = df.withColumn("seller_state", F.upper(F.trim(F.col("seller_state"))))

    log["final_count"] = df.count()
    log["removed_total"] = log["original_count"] - log["final_count"]
    return df, log


def clean_geolocation(df: DataFrame) -> tuple[DataFrame, dict]:
    """
    Deduplicate geolocation by zip code prefix.
    Takes median lat/lng per prefix to get a single representative point.
    """
    log = {"original_count": df.count(), "steps": []}

    df = df.filter(
        F.col("geolocation_zip_code_prefix").isNotNull()
        & F.col("geolocation_lat").isNotNull()
        & F.col("geolocation_lng").isNotNull()
    )

    # Aggregate: one row per zip code prefix with average coordinates
    df_agg = (
        df.groupBy("geolocation_zip_code_prefix")
        .agg(
            F.avg("geolocation_lat").alias("geolocation_lat"),
            F.avg("geolocation_lng").alias("geolocation_lng"),
            F.first("geolocation_city").alias("geolocation_city"),
            F.first("geolocation_state").alias("geolocation_state"),
        )
    )

    log["final_count"] = df_agg.count()
    log["steps"].append(
        f"Deduplicated from {log['original_count']} to {log['final_count']} "
        "unique zip code prefixes (average coordinates)"
    )
    log["removed_total"] = log["original_count"] - log["final_count"]
    return df_agg, log


def clean_all(datasets: dict) -> tuple[dict, dict]:
    """
    Clean all datasets.
    Returns (cleaned_datasets, cleaning_logs).
    """
    cleaners = {
        "orders": clean_orders,
        "order_items": clean_order_items,
        "customers": clean_customers,
        "products": clean_products,
        "payments": clean_payments,
        "reviews": clean_reviews,
        "sellers": clean_sellers,
        "geolocation": clean_geolocation,
    }

    cleaned = {}
    logs = {}

    for name, cleaner in cleaners.items():
        if name in datasets:
            cleaned[name], logs[name] = cleaner(datasets[name])

    # Category translation: just load as-is (no cleaning needed beyond BOM strip)
    if "category_translation" in datasets:
        ct = datasets["category_translation"]
        # Strip BOM that may appear in the first column name
        ct = ct.toDF(*[c.strip("﻿").strip() for c in ct.columns])
        cleaned["category_translation"] = ct
        logs["category_translation"] = {
            "original_count": ct.count(),
            "final_count": ct.count(),
            "removed_total": 0,
            "steps": ["Loaded as-is (reference table)"],
        }

    return cleaned, logs
