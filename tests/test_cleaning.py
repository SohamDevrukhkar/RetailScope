"""
Tests for data cleaning pipeline.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import *
from datetime import date


@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder
        .appName("RetailScope Cleaning Tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


def test_order_duplicate_removal(spark):
    """Duplicate order_ids should be removed, keeping one."""
    from src.data_cleaning import clean_orders

    schema = StructType([
        StructField("order_id", StringType()),
        StructField("customer_id", StringType()),
        StructField("order_status", StringType()),
        StructField("order_purchase_timestamp", StringType()),
        StructField("order_approved_at", StringType()),
        StructField("order_delivered_carrier_date", StringType()),
        StructField("order_delivered_customer_date", StringType()),
        StructField("order_estimated_delivery_date", StringType()),
    ])
    data = [
        ("o1", "c1", "delivered", "2018-01-01 10:00:00",
         "2018-01-01 11:00:00", "2018-01-05 00:00:00",
         "2018-01-08 00:00:00", "2018-01-10 00:00:00"),
        ("o1", "c1", "delivered", "2018-01-01 10:00:00",  # duplicate
         "2018-01-01 11:00:00", "2018-01-05 00:00:00",
         "2018-01-08 00:00:00", "2018-01-10 00:00:00"),
        ("o2", "c2", "shipped", "2018-02-01 10:00:00",
         None, None, None, "2018-02-10 00:00:00"),
    ]
    df = spark.createDataFrame(data, schema)
    cleaned, log = clean_orders(df)

    assert cleaned.count() == 2  # o1 (deduplicated) + o2


def test_null_order_id_removal(spark):
    """Orders with null order_id should be removed."""
    from src.data_cleaning import clean_orders

    schema = StructType([
        StructField("order_id", StringType()),
        StructField("customer_id", StringType()),
        StructField("order_status", StringType()),
        StructField("order_purchase_timestamp", StringType()),
        StructField("order_approved_at", StringType()),
        StructField("order_delivered_carrier_date", StringType()),
        StructField("order_delivered_customer_date", StringType()),
        StructField("order_estimated_delivery_date", StringType()),
    ])
    data = [
        ("o1", "c1", "delivered", "2018-01-01 10:00:00", None, None, None, None),
        (None, "c2", "delivered", "2018-01-01 10:00:00", None, None, None, None),
    ]
    df = spark.createDataFrame(data, schema)
    cleaned, log = clean_orders(df)

    assert cleaned.count() == 1
    assert log["removed_total"] >= 1


def test_review_score_clamping(spark):
    """Review scores outside [1, 5] should be removed."""
    from src.data_cleaning import clean_reviews

    schema = StructType([
        StructField("review_id", StringType()),
        StructField("order_id", StringType()),
        StructField("review_score", IntegerType()),
        StructField("review_comment_title", StringType()),
        StructField("review_comment_message", StringType()),
        StructField("review_creation_date", StringType()),
        StructField("review_answer_timestamp", StringType()),
    ])
    data = [
        ("r1", "o1", 5, None, None, "2018-01-01 00:00:00", "2018-01-02 00:00:00"),
        ("r2", "o2", 0, None, None, "2018-01-01 00:00:00", "2018-01-02 00:00:00"),  # invalid
        ("r3", "o3", 6, None, None, "2018-01-01 00:00:00", "2018-01-02 00:00:00"),  # invalid
        ("r4", "o4", 3, None, None, "2018-01-01 00:00:00", "2018-01-02 00:00:00"),
    ]
    df = spark.createDataFrame(data, schema)
    cleaned, log = clean_reviews(df)

    scores = [r["review_score"] for r in cleaned.collect()]
    assert all(1 <= s <= 5 for s in scores)
    assert cleaned.count() == 2


def test_customer_unique_id_used(spark):
    """Ensure customer_unique_id is present and non-null after cleaning."""
    from src.data_cleaning import clean_customers
    from pyspark.sql import functions as F

    schema = StructType([
        StructField("customer_id", StringType()),
        StructField("customer_unique_id", StringType()),
        StructField("customer_zip_code_prefix", StringType()),
        StructField("customer_city", StringType()),
        StructField("customer_state", StringType()),
    ])
    data = [
        ("c1", "u1", "01001", "São Paulo", "SP"),
        ("c2", "u2", "30130", "BH", "MG"),
        ("c3", None, "90000", "Porto Alegre", "RS"),  # null unique_id → removed
    ]
    df = spark.createDataFrame(data, schema)
    cleaned, log = clean_customers(df)

    null_count = cleaned.filter(F.col("customer_unique_id").isNull()).count()
    assert null_count == 0
    assert cleaned.count() == 2
