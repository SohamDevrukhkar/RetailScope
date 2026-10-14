"""
Data loading module for RetailScope.

Loads all nine Olist CSV files with explicit schemas and correct data types.
Writes cleaned/processed data to Parquet. Reads back from Parquet when available.
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    DoubleType, TimestampType, LongType,
)


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

CUSTOMERS_SCHEMA = StructType([
    StructField("customer_id", StringType(), False),
    StructField("customer_unique_id", StringType(), False),
    StructField("customer_zip_code_prefix", StringType(), True),
    StructField("customer_city", StringType(), True),
    StructField("customer_state", StringType(), True),
])

ORDERS_SCHEMA = StructType([
    StructField("order_id", StringType(), False),
    StructField("customer_id", StringType(), False),
    StructField("order_status", StringType(), True),
    StructField("order_purchase_timestamp", StringType(), True),
    StructField("order_approved_at", StringType(), True),
    StructField("order_delivered_carrier_date", StringType(), True),
    StructField("order_delivered_customer_date", StringType(), True),
    StructField("order_estimated_delivery_date", StringType(), True),
])

ORDER_ITEMS_SCHEMA = StructType([
    StructField("order_id", StringType(), False),
    StructField("order_item_id", IntegerType(), True),
    StructField("product_id", StringType(), True),
    StructField("seller_id", StringType(), True),
    StructField("shipping_limit_date", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("freight_value", DoubleType(), True),
])

PAYMENTS_SCHEMA = StructType([
    StructField("order_id", StringType(), False),
    StructField("payment_sequential", IntegerType(), True),
    StructField("payment_type", StringType(), True),
    StructField("payment_installments", IntegerType(), True),
    StructField("payment_value", DoubleType(), True),
])

REVIEWS_SCHEMA = StructType([
    StructField("review_id", StringType(), True),
    StructField("order_id", StringType(), False),
    StructField("review_score", IntegerType(), True),
    StructField("review_comment_title", StringType(), True),
    StructField("review_comment_message", StringType(), True),
    StructField("review_creation_date", StringType(), True),
    StructField("review_answer_timestamp", StringType(), True),
])

PRODUCTS_SCHEMA = StructType([
    StructField("product_id", StringType(), False),
    StructField("product_category_name", StringType(), True),
    StructField("product_name_lenght", IntegerType(), True),
    StructField("product_description_lenght", IntegerType(), True),
    StructField("product_photos_qty", IntegerType(), True),
    StructField("product_weight_g", IntegerType(), True),
    StructField("product_length_cm", IntegerType(), True),
    StructField("product_height_cm", IntegerType(), True),
    StructField("product_width_cm", IntegerType(), True),
])

SELLERS_SCHEMA = StructType([
    StructField("seller_id", StringType(), False),
    StructField("seller_zip_code_prefix", StringType(), True),
    StructField("seller_city", StringType(), True),
    StructField("seller_state", StringType(), True),
])

GEOLOCATION_SCHEMA = StructType([
    StructField("geolocation_zip_code_prefix", StringType(), True),
    StructField("geolocation_lat", DoubleType(), True),
    StructField("geolocation_lng", DoubleType(), True),
    StructField("geolocation_city", StringType(), True),
    StructField("geolocation_state", StringType(), True),
])

CATEGORY_TRANSLATION_SCHEMA = StructType([
    StructField("product_category_name", StringType(), True),
    StructField("product_category_name_english", StringType(), True),
])


# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

RAW_FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

SCHEMAS = {
    "customers": CUSTOMERS_SCHEMA,
    "orders": ORDERS_SCHEMA,
    "order_items": ORDER_ITEMS_SCHEMA,
    "payments": PAYMENTS_SCHEMA,
    "reviews": REVIEWS_SCHEMA,
    "products": PRODUCTS_SCHEMA,
    "sellers": SELLERS_SCHEMA,
    "geolocation": GEOLOCATION_SCHEMA,
    "category_translation": CATEGORY_TRANSLATION_SCHEMA,
}


def _raw_dir():
    return os.getenv("RAW_DATA_DIR", "data/raw")


def _processed_dir():
    return os.getenv("PROCESSED_DATA_DIR", "data/processed")


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_raw_csv(spark: SparkSession, name: str):
    """Load a single raw CSV file by dataset name."""
    path = os.path.join(_raw_dir(), RAW_FILES[name])
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset file not found: {path}\n"
            f"Please place the Olist CSV files in '{_raw_dir()}/'."
        )
    schema = SCHEMAS[name]
    df = (
        spark.read
        .option("header", "true")
        .option("quote", '"')
        .option("escape", '"')
        .option("multiLine", "true")
        .schema(schema)
        .csv(path)
    )
    return df


def load_all_raw(spark: SparkSession) -> dict:
    """Load all raw CSV files. Returns dict[name -> DataFrame]."""
    datasets = {}
    missing = []
    for name in RAW_FILES:
        try:
            datasets[name] = load_raw_csv(spark, name)
        except FileNotFoundError as e:
            missing.append(str(e))
    if missing:
        raise FileNotFoundError("\n".join(missing))
    return datasets


def save_parquet(df, name: str, mode: str = "overwrite"):
    """Save a DataFrame as Parquet in the processed directory and register Hive table if enabled."""
    path = os.path.join(_processed_dir(), name)
    df.write.mode(mode).parquet(path)
    try:
        from src.spark_session import is_hive_enabled
        if is_hive_enabled():
            df.write.mode(mode).saveAsTable(name)
    except Exception:
        pass
    return path


def load_parquet(spark: SparkSession, name: str):
    """Load an analytical dataset from Hive (if enabled) or Parquet."""
    try:
        from src.spark_session import is_hive_enabled
        if is_hive_enabled():
            return spark.table(name)
    except Exception:
        pass

    path = os.path.join(_processed_dir(), name)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Processed dataset not found: {path}\n"
            "Run 'python scripts/run_pipeline.py' first."
        )
    return spark.read.parquet(path)


def processed_data_exists() -> bool:
    """Check whether the processed Parquet files exist."""
    proc_dir = _processed_dir()
    expected = [
        "orders_clean", "order_items_clean", "customers_clean",
        "products_clean", "payments_clean", "reviews_clean",
        "sellers_clean", "category_translation",
        "order_metrics", "customer_rfm",
    ]
    return all(
        os.path.exists(os.path.join(proc_dir, n)) for n in expected
    )


def get_raw_file_info() -> list[dict]:
    """Return info about raw CSV files: name, exists, size."""
    info = []
    raw = _raw_dir()
    for name, fname in RAW_FILES.items():
        path = os.path.join(raw, fname)
        exists = os.path.exists(path)
        size_mb = round(os.path.getsize(path) / 1024 / 1024, 2) if exists else 0
        info.append({"name": name, "file": fname, "exists": exists, "size_mb": size_mb})
    return info
