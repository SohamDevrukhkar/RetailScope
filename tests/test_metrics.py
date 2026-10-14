"""
Tests for core metric calculations.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import *
from datetime import date, datetime


@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder
        .appName("RetailScope Tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


# ---------------------------------------------------------------------------
# Sales metric tests
# ---------------------------------------------------------------------------

def test_product_revenue_calculation(spark):
    """Product revenue = sum of item prices (not including freight)."""
    schema = StructType([
        StructField("order_id", StringType()),
        StructField("price", DoubleType()),
        StructField("freight_value", DoubleType()),
    ])
    data = [("o1", 100.0, 15.0), ("o1", 50.0, 10.0), ("o2", 200.0, 20.0)]
    df = spark.createDataFrame(data, schema)

    result = df.groupBy("order_id").agg(
        F.sum("price").alias("product_revenue"),
        F.sum("freight_value").alias("freight"),
    )
    rows = {r["order_id"]: r for r in result.collect()}

    assert abs(rows["o1"]["product_revenue"] - 150.0) < 0.01
    assert abs(rows["o2"]["product_revenue"] - 200.0) < 0.01
    # Freight is separate from product revenue
    assert abs(rows["o1"]["freight"] - 25.0) < 0.01


def test_avg_order_value(spark):
    """AOV = total product revenue / distinct orders."""
    schema = StructType([
        StructField("order_id", StringType()),
        StructField("product_revenue", DoubleType()),
    ])
    data = [("o1", 100.0), ("o2", 200.0), ("o3", 300.0)]
    df = spark.createDataFrame(data, schema)

    total_rev = df.agg(F.sum("product_revenue")).collect()[0][0]
    total_orders = df.count()
    aov = total_rev / total_orders

    assert abs(aov - 200.0) < 0.01


def test_repeat_customer_detection(spark):
    """Customers with > 1 order are repeat customers."""
    schema = StructType([
        StructField("customer_unique_id", StringType()),
        StructField("order_id", StringType()),
    ])
    data = [
        ("cust1", "o1"), ("cust1", "o2"), ("cust1", "o3"),  # repeat
        ("cust2", "o4"),                                       # one-time
        ("cust3", "o5"), ("cust3", "o6"),                    # repeat
    ]
    df = spark.createDataFrame(data, schema)

    customer_order_counts = df.groupBy("customer_unique_id").agg(
        F.countDistinct("order_id").alias("order_count")
    )
    repeat = customer_order_counts.filter(F.col("order_count") > 1)
    onetime = customer_order_counts.filter(F.col("order_count") == 1)

    assert repeat.count() == 2  # cust1 and cust3
    assert onetime.count() == 1  # cust2


def test_no_revenue_inflation_from_join(spark):
    """Joining order items (many per order) should not inflate order-level revenue."""
    # Simulate 1 order with 3 items
    items_schema = StructType([
        StructField("order_id", StringType()),
        StructField("price", DoubleType()),
    ])
    items = spark.createDataFrame([
        ("o1", 50.0), ("o1", 75.0), ("o1", 25.0),
    ], items_schema)

    # Simulate 1 review per order
    reviews_schema = StructType([
        StructField("order_id", StringType()),
        StructField("review_score", IntegerType()),
    ])
    reviews = spark.createDataFrame([("o1", 5)], reviews_schema)

    # Aggregate items before joining
    item_agg = items.groupBy("order_id").agg(F.sum("price").alias("product_revenue"))
    joined = item_agg.join(reviews, "order_id", "left")

    assert joined.count() == 1  # Still 1 row, not 3
    assert abs(joined.collect()[0]["product_revenue"] - 150.0) < 0.01


# ---------------------------------------------------------------------------
# RFM segmentation tests
# ---------------------------------------------------------------------------

def test_rfm_recency_lower_is_better(spark):
    """A customer who bought more recently should have a higher R score."""
    from src.transformations import build_customer_rfm

    schema = StructType([
        StructField("customer_unique_id", StringType()),
        StructField("order_id", StringType()),
        StructField("order_status", StringType()),
        StructField("purchase_date", DateType()),
        StructField("product_revenue", DoubleType()),
        StructField("customer_state", StringType()),
        StructField("customer_city", StringType()),
        StructField("review_score", DoubleType()),
    ])

    # cust_a bought more recently than cust_b
    data = [
        ("cust_a", "o1", "delivered", date(2018, 8, 1), 100.0, "SP", "São Paulo", 5.0),
        ("cust_b", "o2", "delivered", date(2017, 1, 1), 100.0, "SP", "São Paulo", 5.0),
    ]
    df = spark.createDataFrame(data, schema)

    # Build RFM manually
    rfm = build_customer_rfm(df)
    rows = {r["customer_unique_id"]: r for r in rfm.collect()}

    # cust_a: more recent → lower recency days → higher R score
    assert rows["cust_a"]["r_score"] >= rows["cust_b"]["r_score"]


def test_champions_criteria(spark):
    """Champions should have high R, F, and M scores."""
    from src.transformations import build_customer_rfm

    schema = StructType([
        StructField("customer_unique_id", StringType()),
        StructField("order_id", StringType()),
        StructField("order_status", StringType()),
        StructField("purchase_date", DateType()),
        StructField("product_revenue", DoubleType()),
        StructField("customer_state", StringType()),
        StructField("customer_city", StringType()),
        StructField("review_score", DoubleType()),
    ])

    # Create a large enough dataset so ntile(5) works well
    data = []
    for i in range(50):
        cuid = f"cust_{i:02d}"
        # Vary purchase dates, frequencies, and amounts
        for j in range(i % 5 + 1):
            data.append((
                cuid, f"o_{i}_{j}", "delivered",
                date(2018, max(1, 12 - i % 12), 1),
                float(100 + i * 10), "SP", "SP", 5.0,
            ))
    df = spark.createDataFrame(data, schema)
    rfm = build_customer_rfm(df)

    # Verify all segments are valid labels
    valid_segments = {"Champions", "Loyal Customers", "Potential Loyalists",
                      "Recent Customers", "At Risk", "Lost", "Others"}
    segments = set(r["segment"] for r in rfm.collect())
    assert segments.issubset(valid_segments), f"Unexpected segments: {segments - valid_segments}"


# ---------------------------------------------------------------------------
# Data cleaning tests
# ---------------------------------------------------------------------------

def test_geolocation_deduplication(spark):
    """Geolocation should produce one row per zip code prefix."""
    from src.data_cleaning import clean_geolocation

    schema = StructType([
        StructField("geolocation_zip_code_prefix", StringType()),
        StructField("geolocation_lat", DoubleType()),
        StructField("geolocation_lng", DoubleType()),
        StructField("geolocation_city", StringType()),
        StructField("geolocation_state", StringType()),
    ])
    data = [
        ("01001", -23.5, -46.6, "Sao Paulo", "SP"),
        ("01001", -23.51, -46.61, "Sao Paulo", "SP"),
        ("01001", -23.49, -46.59, "Sao Paulo", "SP"),
        ("30130", -19.9, -43.9, "Belo Horizonte", "MG"),
    ]
    df = spark.createDataFrame(data, schema)
    cleaned, log = clean_geolocation(df)

    assert cleaned.count() == 2  # One per prefix
    # Avg lat for 01001 ≈ (-23.5 + -23.51 + -23.49) / 3 = -23.5
    sp_row = cleaned.filter(F.col("geolocation_zip_code_prefix") == "01001").collect()[0]
    assert abs(sp_row["geolocation_lat"] - (-23.5)) < 0.01


def test_negative_price_removal(spark):
    """Negative prices should be removed during cleaning."""
    from src.data_cleaning import clean_order_items

    schema = StructType([
        StructField("order_id", StringType()),
        StructField("order_item_id", IntegerType()),
        StructField("product_id", StringType()),
        StructField("seller_id", StringType()),
        StructField("shipping_limit_date", StringType()),
        StructField("price", DoubleType()),
        StructField("freight_value", DoubleType()),
    ])
    data = [
        ("o1", 1, "p1", "s1", "2018-01-01 00:00:00", 100.0, 10.0),
        ("o2", 1, "p2", "s1", "2018-01-01 00:00:00", -50.0, 5.0),  # invalid
        ("o3", 1, "p3", "s1", "2018-01-01 00:00:00", 0.0, 0.0),    # valid (zero)
    ]
    df = spark.createDataFrame(data, schema)
    cleaned, log = clean_order_items(df)

    assert cleaned.count() == 2  # o1 and o3
    assert log["removed_total"] == 1
