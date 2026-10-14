# RetailScope — Customer Purchase Intelligence

> **Big Data Analysis Mini Project · Semester 7 B.Tech Computer Engineering**  
> Real-time analytics on the Brazilian E-Commerce Public Dataset by Olist using PySpark, Parquet, and Streamlit.

---

## Overview

RetailScope is a fully functional, interactive business intelligence dashboard that analyses ~100,000 real e-commerce orders from the Olist marketplace. It provides:

- **Business KPIs** — Revenue, orders, customers, AOV, repeat-purchase rate, review scores
- **Sales Trends** — Daily / monthly / yearly revenue, weekday patterns, seasonality
- **Customer Segmentation** — RFM scoring and segment classification (Champions, Loyal, At Risk, etc.)
- **Product Analytics** — Top products, category revenue, pricing, slow movers
- **Geographic Analytics** — State and regional breakdown for customers and sellers
- **Order Intelligence** — Delivery performance, payment methods, installments, satisfaction
- **Insights Engine** — Auto-generated data-driven business insights

---

## Key Features

| Feature | Technology |
|---|---|
| Large-scale data processing | PySpark (local mode) |
| Columnar storage | Apache Parquet (Snappy compression) |
| Optional SQL analytics | Apache Hive via `enableHiveSupport()` |
| Interactive dashboards | Streamlit |
| Charts and graphs | Plotly |
| Display aggregations | Pandas (small results only) |

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.10+ | 3.11 or 3.12 |
| Java | 11 | 11 or 17 (not 21+) |
| RAM | 8 GB | 16 GB |
| Disk | 2 GB free | 5 GB free |

> **Java note:** PySpark 3.5 requires Java 8, 11, or 17. Java 21+ may cause issues. Verify with `java -version`.

---

## Installation

### 1. Clone or set up the project

```bash
cd /path/to/BDA
```

### 2. Create and activate a virtual environment

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Dataset Setup

Place all nine Olist CSV files inside `data/raw/`:

```
data/raw/
├── olist_customers_dataset.csv
├── olist_geolocation_dataset.csv
├── olist_order_items_dataset.csv
├── olist_order_payments_dataset.csv
├── olist_order_reviews_dataset.csv
├── olist_orders_dataset.csv
├── olist_products_dataset.csv
├── olist_sellers_dataset.csv
└── product_category_name_translation.csv
```

Dataset source: [Kaggle — Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

---

## Environment Configuration

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

```env
# Set to true if you have a Hive metastore configured
HIVE_ENABLED=false

# Spark driver memory (increase for large machines)
SPARK_DRIVER_MEMORY=4g

# Data directories
RAW_DATA_DIR=data/raw
PROCESSED_DATA_DIR=data/processed
```

---

## Running the Pipeline

Run the data processing pipeline once before launching the app:

```bash
python scripts/run_pipeline.py
```

The pipeline:
1. Checks that all CSV files exist
2. Loads every dataset with the correct schema
3. Runs data quality checks (null counts, duplicates, invalid values)
4. Cleans each dataset with documented rules
5. Builds analytical tables: `order_metrics`, `customer_rfm`, `item_data`
6. Writes Parquet output to `data/processed/`

**Expected runtime:** 2–6 minutes depending on hardware.

### Rebuild after data change

```bash
python scripts/run_pipeline.py --rebuild
```

---

## Launching the Application

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Use the sidebar to navigate between pages.

---

## Hive Integration

RetailScope supports Apache Hive as an alternative storage backend.

To enable it:

1. Install Hadoop and configure a Hive metastore.
2. Set `HIVE_ENABLED=true` in `.env`.
3. Run the pipeline — it will create Hive tables alongside the Parquet files.

When Hive is unavailable, the application falls back to local Parquet mode and clearly states which backend is active. It **never falsely claims Hive is running**.

---

## Project Architecture

```
retailscope/
├── app.py                      ← Streamlit home page
├── pages/
│   ├── 1_Business_Overview.py
│   ├── 2_Sales_Trends.py
│   ├── 3_Customer_Analytics.py
│   ├── 4_Product_Analytics.py
│   ├── 5_Geographic_Analytics.py
│   ├── 6_Orders_Payments_Reviews.py
│   └── 7_Business_Insights.py
├── src/
│   ├── spark_session.py        ← SparkSession management
│   ├── data_loader.py          ← CSV schemas and Parquet I/O
│   ├── data_cleaning.py        ← Cleaning with audit logs
│   ├── transformations.py      ← order_metrics, customer_rfm, item_data
│   ├── sales_analytics.py      ← KPIs and time-series aggregations
│   ├── customer_segmentation.py← RFM scoring and segment labels
│   ├── product_analytics.py    ← Product/category analytics
│   ├── geographic_analytics.py ← State/region analytics
│   ├── order_analytics.py      ← Delivery, payments, reviews
│   ├── insights.py             ← Data-driven insight generation
│   └── ui_utils.py             ← Streamlit helpers, CSS, caching
├── scripts/
│   └── run_pipeline.py         ← End-to-end pipeline runner
├── tests/
│   ├── test_metrics.py         ← Metric calculation tests
│   └── test_cleaning.py        ← Data cleaning tests
├── data/
│   ├── raw/                    ← Input CSV files (not committed)
│   └── processed/              ← Parquet output (not committed)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

### Data Flow

```
Raw CSVs (data/raw/)
    │
    ▼
[run_pipeline.py]
    │
    ├── Quality checks (null counts, duplicates, invalid values)
    │
    ├── Cleaning (per-dataset documented rules)
    │
    ├── Transformations
    │   ├── order_metrics    — order-level denormalized table
    │   ├── customer_rfm     — RFM scores and segments
    │   └── item_data        — item-level with product/category details
    │
    └── Parquet storage (data/processed/)
            │
            ▼
    [Streamlit app] ← reads Parquet, caches in-memory, renders dashboards
```

---

## Analytical Metric Definitions

| Metric | Definition |
|---|---|
| **Product Revenue** | Σ(item price) — excludes freight |
| **Avg Order Value** | Product revenue ÷ distinct orders |
| **Repeat Customer** | customer_unique_id with > 1 distinct order |
| **Repeat Rate** | Repeat customers ÷ total customers |
| **Recency (R)** | Days from last purchase to reference date |
| **Frequency (F)** | Count of distinct orders per customer_unique_id |
| **Monetary (M)** | Total product revenue per customer_unique_id |
| **RFM Score** | Quintile-based 1–5 per dimension; higher = better |
| **Delivery Delay** | Actual delivery − Estimated delivery (positive = late) |

Customer identity uses `customer_unique_id` (not `customer_id`) to correctly
track buyers across multiple orders.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests cover: revenue calculation, repeat-customer detection, join inflation prevention,
RFM scoring direction, geolocation deduplication, price validation, and null handling.

---

## Common Errors

| Error | Solution |
|---|---|
| `FileNotFoundError: data/raw/...` | Place all 9 CSV files in `data/raw/` |
| `FileNotFoundError: data/processed/...` | Run `python scripts/run_pipeline.py` first |
| `Java not found` | Install Java 11 or 17 and set `JAVA_HOME` |
| `SparkException: Java heap space` | Increase `SPARK_DRIVER_MEMORY` in `.env` |
| `Hive not available` | Set `HIVE_ENABLED=false` — Parquet mode will be used |
| `Port 8501 already in use` | Run `streamlit run app.py --server.port 8502` |

---

## Data Quality Notes

The pipeline documents every exclusion:
- Orders with null `order_id` or `customer_id` are removed
- Reviews outside score range [1, 5] are removed  
- Negative item prices are removed (zero prices are retained)
- Duplicate orders are deduplicated by `order_id`
- Geolocation records are aggregated to one row per zip code prefix
- Cancelled orders are included in the data but excluded from RFM calculation

A cleaning log is printed during pipeline execution showing record counts before and after each step.
