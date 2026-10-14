#!/usr/bin/env python3
"""
RetailScope — Data Pipeline Runner

Loads raw Olist CSV files, runs data quality checks, cleans data,
builds analytical tables, and writes Parquet output.

Usage:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --rebuild   # Force rebuild even if processed data exists
"""

import sys
import os
import time
import argparse

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from src.spark_session import get_spark_session, get_storage_mode
from src.data_loader import load_all_raw, save_parquet, get_raw_file_info
from src.data_cleaning import run_quality_checks, clean_all
from src.transformations import build_order_metrics, build_customer_rfm, build_item_level_data


def print_section(title: str):
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_quality_report(report: dict):
    for name, info in report.items():
        print(f"\n  [{name}]")
        print(f"    Records       : {info['total_records']:,}")
        print(f"    Duplicates    : {info.get('duplicate_records', 0):,}")
        if info.get("null_counts"):
            for col, cnt in info["null_counts"].items():
                print(f"    Null [{col}]: {cnt:,}")
        if "cancelled_orders" in info:
            print(f"    Cancelled     : {info['cancelled_orders']:,}")
        if "negative_prices" in info:
            print(f"    Negative prices: {info['negative_prices']:,}")


def print_cleaning_logs(logs: dict):
    for name, log in logs.items():
        removed = log.get("removed_total", 0)
        print(f"\n  [{name}]")
        print(f"    Before: {log['original_count']:,}  →  After: {log['final_count']:,}  (removed {removed:,})")
        for step in log.get("steps", []):
            print(f"      • {step}")


def main():
    parser = argparse.ArgumentParser(description="RetailScope Data Pipeline")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild of processed data")
    args = parser.parse_args()

    start_time = time.time()
    print()
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║   RetailScope — Customer Purchase Intelligence   ║")
    print("  ║              Data Processing Pipeline            ║")
    print("  ╚══════════════════════════════════════════════════╝")

    # -----------------------------------------------------------------------
    print_section("Step 0 · Environment Check")
    # -----------------------------------------------------------------------

    print("\n  Storage mode:", get_storage_mode() if False else "Will be determined after Spark init")

    raw_files = get_raw_file_info()
    print("\n  Raw data files:")
    all_found = True
    for f in raw_files:
        status = "✓" if f["exists"] else "✗"
        size = f"{f['size_mb']} MB" if f["exists"] else "MISSING"
        print(f"    {status}  {f['file']:50s}  {size}")
        if not f["exists"]:
            all_found = False

    if not all_found:
        print("\n  ERROR: One or more dataset files are missing.")
        print("  Please place all Olist CSV files in 'data/raw/'.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    print_section("Step 1 · Spark Session Initialisation")
    # -----------------------------------------------------------------------

    print("\n  Starting SparkSession …", end=" ", flush=True)
    spark = get_spark_session()
    print("done")
    print(f"  Storage mode: {get_storage_mode()}")
    print(f"  Spark version: {spark.version}")

    # -----------------------------------------------------------------------
    print_section("Step 2 · Loading Raw CSV Files")
    # -----------------------------------------------------------------------

    print("\n  Loading all datasets …")
    datasets = load_all_raw(spark)
    for name, df in datasets.items():
        print(f"    {name:30s}: {df.count():>7,} rows, {len(df.columns)} columns")

    # -----------------------------------------------------------------------
    print_section("Step 3 · Data Quality Checks")
    # -----------------------------------------------------------------------

    print("\n  Running quality checks …")
    quality_report = run_quality_checks(datasets)
    print_quality_report(quality_report)

    # -----------------------------------------------------------------------
    print_section("Step 4 · Data Cleaning")
    # -----------------------------------------------------------------------

    print("\n  Cleaning all datasets …")
    cleaned, cleaning_logs = clean_all(datasets)
    print_cleaning_logs(cleaning_logs)

    # -----------------------------------------------------------------------
    print_section("Step 5 · Building Analytical Tables")
    # -----------------------------------------------------------------------

    print("\n  Building order metrics …")
    order_metrics = build_order_metrics(
        orders=cleaned["orders"],
        order_items=cleaned["order_items"],
        customers=cleaned["customers"],
        products=cleaned["products"],
        category_translation=cleaned["category_translation"],
        reviews=cleaned["reviews"],
        payments=cleaned["payments"],
    )
    order_count = order_metrics.count()
    print(f"    Order metrics rows: {order_count:,}")

    print("  Building customer RFM …")
    customer_rfm = build_customer_rfm(order_metrics)
    rfm_count = customer_rfm.count()
    print(f"    Customer RFM rows: {rfm_count:,}")

    print("  Building item-level data …")
    item_data = build_item_level_data(
        order_items=cleaned["order_items"],
        products=cleaned["products"],
        category_translation=cleaned["category_translation"],
        orders=cleaned["orders"],
        customers=cleaned["customers"],
    )
    item_count = item_data.count()
    print(f"    Item-level data rows: {item_count:,}")

    # -----------------------------------------------------------------------
    print_section("Step 6 · Writing Parquet Output")
    # -----------------------------------------------------------------------

    print("\n  Saving cleaned datasets …")
    tables_to_save = {
        "orders_clean": cleaned["orders"],
        "order_items_clean": cleaned["order_items"],
        "customers_clean": cleaned["customers"],
        "products_clean": cleaned["products"],
        "payments_clean": cleaned["payments"],
        "reviews_clean": cleaned["reviews"],
        "sellers_clean": cleaned["sellers"],
        "geolocation_clean": cleaned["geolocation"],
        "category_translation": cleaned["category_translation"],
        "order_metrics": order_metrics,
        "customer_rfm": customer_rfm,
        "item_data": item_data,
    }

    for name, df in tables_to_save.items():
        path = save_parquet(df, name)
        print(f"    Saved: {path}")

    # -----------------------------------------------------------------------
    print_section("Pipeline Complete")
    # -----------------------------------------------------------------------

    elapsed = round(time.time() - start_time, 1)
    print(f"\n  Total time: {elapsed}s")
    print(f"  Storage mode: {get_storage_mode()}")
    print(f"  Processed data written to: {os.path.abspath('data/processed/')}")
    print()
    print("  Next step:")
    print("    streamlit run app.py")
    print()

    spark.stop()


if __name__ == "__main__":
    main()
