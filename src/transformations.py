"""
Core transformations for RetailScope.

Joins cleaned datasets to produce analytical tables:
- order_metrics: one row per order with revenue, customer, timing info
- customer_rfm: one row per customer_unique_id with RFM scores and segments
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def build_order_metrics(
    orders: DataFrame,
    order_items: DataFrame,
    customers: DataFrame,
    products: DataFrame,
    category_translation: DataFrame,
    reviews: DataFrame,
    payments: DataFrame,
) -> DataFrame:
    """
    Build a denormalized order-level metrics table.

    Aggregates order_items per order BEFORE joining to prevent row inflation.
    """

    # --- Aggregate order items per order ---
    order_item_agg = (
        order_items
        .groupBy("order_id")
        .agg(
            F.sum("price").alias("product_revenue"),
            F.sum("freight_value").alias("total_freight"),
            F.count("*").alias("item_count"),
            F.countDistinct("product_id").alias("distinct_products"),
        )
    )

    # --- Build product info for top-product analysis (keep item-level) ---
    # We store the category of the most expensive item in the order for simple categorization
    items_with_product = order_items.join(products, "product_id", "left")
    items_with_cat = items_with_product.join(
        category_translation, "product_category_name", "left"
    )

    # Pick the primary category per order (the category of the highest-revenue item)
    w = Window.partitionBy("order_id").orderBy(F.col("price").desc())
    primary_cat = (
        items_with_cat
        .withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .select(
            "order_id",
            F.coalesce(
                F.col("product_category_name_english"),
                F.col("product_category_name"),
            ).alias("primary_category"),
        )
    )

    # --- Aggregate reviews per order (already deduplicated, but just in case) ---
    review_agg = (
        reviews
        .groupBy("order_id")
        .agg(F.avg("review_score").alias("review_score"))
    )

    # --- Aggregate payments per order ---
    payment_agg = (
        payments
        .groupBy("order_id")
        .agg(
            F.sum("payment_value").alias("payment_value"),
            F.first("payment_type").alias("primary_payment_type"),
            F.max("payment_installments").alias("max_installments"),
        )
    )

    # --- Join everything at order level ---
    order_metrics = (
        orders
        .join(order_item_agg, "order_id", "inner")  # Only orders with items
        .join(customers, "customer_id", "inner")
        .join(primary_cat, "order_id", "left")
        .join(review_agg, "order_id", "left")
        .join(payment_agg, "order_id", "left")
    )

    # --- Compute delivery metrics ---
    order_metrics = order_metrics.withColumn(
        "delivery_days",
        F.when(
            F.col("order_delivered_customer_date").isNotNull()
            & F.col("order_purchase_timestamp").isNotNull(),
            F.datediff(
                F.col("order_delivered_customer_date"),
                F.col("order_purchase_timestamp"),
            ),
        ),
    )

    order_metrics = order_metrics.withColumn(
        "estimated_delivery_days",
        F.when(
            F.col("order_estimated_delivery_date").isNotNull()
            & F.col("order_purchase_timestamp").isNotNull(),
            F.datediff(
                F.col("order_estimated_delivery_date"),
                F.col("order_purchase_timestamp"),
            ),
        ),
    )

    order_metrics = order_metrics.withColumn(
        "delivery_delay_days",
        F.when(
            F.col("order_delivered_customer_date").isNotNull()
            & F.col("order_estimated_delivery_date").isNotNull(),
            F.datediff(
                F.col("order_delivered_customer_date"),
                F.col("order_estimated_delivery_date"),
            ),
        ),
    )

    order_metrics = order_metrics.withColumn(
        "is_late",
        F.when(F.col("delivery_delay_days") > 0, True).otherwise(False),
    )

    # Add date parts for time-series analysis
    order_metrics = (
        order_metrics
        .withColumn("purchase_date", F.to_date("order_purchase_timestamp"))
        .withColumn("purchase_year", F.year("order_purchase_timestamp"))
        .withColumn("purchase_month", F.month("order_purchase_timestamp"))
        .withColumn("purchase_year_month", F.date_format("order_purchase_timestamp", "yyyy-MM"))
        .withColumn("purchase_day_of_week", F.dayofweek("order_purchase_timestamp"))
        .withColumn("purchase_hour", F.hour("order_purchase_timestamp"))
    )

    return order_metrics


def build_customer_rfm(order_metrics: DataFrame) -> DataFrame:
    """
    Compute RFM (Recency, Frequency, Monetary) segmentation.

    Uses customer_unique_id to track customers across orders.
    Reference date = max purchase date in the dataset + 1 day.
    """

    # Only use delivered or shipped orders for RFM (exclude cancelled)
    valid_orders = order_metrics.filter(
        F.col("order_status").isin("delivered", "shipped", "invoiced", "processing", "approved")
    )

    # Reference date: max purchase date + 1
    ref_row = valid_orders.agg(F.max("purchase_date")).collect()
    ref_date = ref_row[0][0]
    if ref_date is None:
        raise ValueError("No valid orders found for RFM calculation")

    from datetime import timedelta
    ref_date = ref_date + timedelta(days=1)

    # Customer-level aggregation
    customer_agg = (
        valid_orders
        .groupBy("customer_unique_id")
        .agg(
            F.max("purchase_date").alias("last_purchase_date"),
            F.countDistinct("order_id").alias("frequency"),
            F.sum("product_revenue").alias("monetary"),
            F.min("purchase_date").alias("first_purchase_date"),
            F.avg("review_score").alias("avg_review_score"),
            F.first("customer_state").alias("customer_state"),
            F.first("customer_city").alias("customer_city"),
        )
    )

    # Recency: days since last purchase
    customer_agg = customer_agg.withColumn(
        "recency",
        F.datediff(F.lit(ref_date), F.col("last_purchase_date")),
    )

    # RFM scoring (1-5 scale using quantiles)
    # We use ntile to split into 5 roughly equal groups
    # Recency: lower = better → score 5 for most recent
    # Frequency: higher = better → score 5 for most frequent
    # Monetary: higher = better → score 5 for highest spenders

    w_r = Window.orderBy(F.col("recency").asc(), F.col("customer_unique_id").asc())   # lower recency → higher rank
    w_f = Window.orderBy(F.col("frequency").asc(), F.col("customer_unique_id").asc())
    w_m = Window.orderBy(F.col("monetary").asc(), F.col("customer_unique_id").asc())

    customer_rfm = (
        customer_agg
        .withColumn("r_score", 6 - F.ntile(5).over(w_r))  # Invert: 1→5, 5→1
        .withColumn("f_score", F.ntile(5).over(w_f))
        .withColumn("m_score", F.ntile(5).over(w_m))
    )

    customer_rfm = customer_rfm.withColumn(
        "rfm_score",
        F.col("r_score") * 100 + F.col("f_score") * 10 + F.col("m_score"),
    )

    # Segment assignment based on RFM scores
    customer_rfm = customer_rfm.withColumn(
        "segment",
        F.when(
            (F.col("r_score") >= 4) & (F.col("f_score") >= 4) & (F.col("m_score") >= 4),
            "Champions",
        )
        .when(
            (F.col("r_score") >= 3) & (F.col("f_score") >= 3) & (F.col("m_score") >= 3),
            "Loyal Customers",
        )
        .when(
            (F.col("r_score") >= 4) & (F.col("f_score") <= 2),
            "Recent Customers",
        )
        .when(
            (F.col("r_score") >= 3) & (F.col("f_score") >= 2) & (F.col("m_score") >= 2),
            "Potential Loyalists",
        )
        .when(
            (F.col("r_score") <= 2) & (F.col("f_score") >= 3),
            "At Risk",
        )
        .when(
            (F.col("r_score") <= 2) & (F.col("f_score") <= 2),
            "Lost",
        )
        .otherwise("Others"),
    )

    customer_rfm = customer_rfm.withColumn(
        "is_repeat", F.when(F.col("frequency") > 1, True).otherwise(False)
    )

    customer_rfm = customer_rfm.withColumn("rfm_reference_date", F.lit(ref_date))

    return customer_rfm


def build_item_level_data(
    order_items: DataFrame,
    products: DataFrame,
    category_translation: DataFrame,
    orders: DataFrame,
    customers: DataFrame,
) -> DataFrame:
    """
    Build item-level dataset with product details and English category names.
    Used for product/category analytics.
    """
    items = (
        order_items
        .join(products, "product_id", "left")
        .join(category_translation, "product_category_name", "left")
        .join(
            orders.select("order_id", "customer_id", "order_status",
                          "order_purchase_timestamp"),
            "order_id", "inner",
        )
        .join(
            customers.select("customer_id", "customer_unique_id", "customer_state"),
            "customer_id", "left",
        )
    )

    items = items.withColumn(
        "category_english",
        F.coalesce(
            F.col("product_category_name_english"),
            F.col("product_category_name"),
            F.lit("Unknown"),
        ),
    )

    items = items.withColumn(
        "item_revenue", F.col("price")
    )

    items = (
        items
        .withColumn("purchase_date", F.to_date("order_purchase_timestamp"))
        .withColumn("purchase_year_month", F.date_format("order_purchase_timestamp", "yyyy-MM"))
    )

    return items
