"""
Spark session management for RetailScope.

Creates a SparkSession in local mode, optionally with Hive support.
Reports which storage mode is active (Hive or Parquet-local).
"""

import os
from pyspark.sql import SparkSession

_spark = None
_hive_enabled = False


def _create_builder(driver_memory: str):
    return (
        SparkSession.builder
        .appName("RetailScope — Customer Purchase Intelligence")
        .master("local[*]")
        .config("spark.driver.memory", driver_memory)
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.session.timeZone", "America/Sao_Paulo")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.ui.showConsoleProgress", "false")
    )


def get_spark_session():
    """Return a singleton SparkSession, creating it on first call."""
    global _spark, _hive_enabled
    if _spark is not None:
        return _spark

    hive_flag = os.getenv("HIVE_ENABLED", "false").lower() == "true"
    driver_memory = os.getenv("SPARK_DRIVER_MEMORY", "4g")

    if hive_flag:
        try:
            builder = _create_builder(driver_memory).enableHiveSupport()
            _spark = builder.getOrCreate()
            # Verify Hive is actually working
            _spark.sql("SHOW DATABASES").collect()
            _hive_enabled = True
        except Exception:
            # Fall back to plain session if Hive fails
            _spark = None
            _hive_enabled = False

    if _spark is None:
        _spark = _create_builder(driver_memory).getOrCreate()
        _hive_enabled = False

    _spark.sparkContext.setLogLevel("WARN")
    return _spark


def is_hive_enabled():
    """Return True if the active session has working Hive support."""
    return _hive_enabled


def get_storage_mode():
    """Return a human-readable string describing the storage backend."""
    if _hive_enabled:
        return "Apache Hive (via Spark SQL)"
    return "Local Parquet files"


def stop_spark():
    """Stop the SparkSession if running."""
    global _spark
    if _spark is not None:
        _spark.stop()
        _spark = None
