"""
Geographic analytics for RetailScope.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


# Brazilian state-to-region mapping
STATE_REGION = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte",
    "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

# Full state names
STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}


def _add_region(df: DataFrame, state_col: str = "customer_state") -> DataFrame:
    """Add a 'region' column based on state code."""
    mapping_expr = F.create_map([F.lit(x) for kv in STATE_REGION.items() for x in kv])
    return df.withColumn("region", mapping_expr[F.col(state_col)])


def orders_by_state(order_metrics: DataFrame) -> DataFrame:
    """Orders and revenue grouped by customer state."""
    result = (
        order_metrics
        .filter(F.col("customer_state").isNotNull())
        .groupBy("customer_state")
        .agg(
            F.countDistinct("order_id").alias("orders"),
            F.sum("product_revenue").alias("revenue"),
            F.countDistinct("customer_unique_id").alias("customers"),
        )
        .orderBy(F.col("revenue").desc())
    )
    return _add_region(result)


def seller_distribution(order_metrics: DataFrame, sellers: DataFrame) -> DataFrame:
    """Sellers by state."""
    return (
        sellers
        .filter(F.col("seller_state").isNotNull())
        .groupBy("seller_state")
        .agg(F.countDistinct("seller_id").alias("seller_count"))
        .orderBy(F.col("seller_count").desc())
    )


def revenue_by_region(order_metrics: DataFrame) -> DataFrame:
    """Revenue grouped by Brazilian region."""
    df = _add_region(order_metrics)
    return (
        df
        .filter(F.col("region").isNotNull())
        .groupBy("region")
        .agg(
            F.sum("product_revenue").alias("revenue"),
            F.countDistinct("order_id").alias("orders"),
            F.countDistinct("customer_unique_id").alias("customers"),
        )
        .orderBy(F.col("revenue").desc())
    )


def customer_seller_comparison(order_metrics: DataFrame, sellers: DataFrame) -> tuple:
    """Side-by-side customer vs seller state distribution."""
    cust_by_state = (
        order_metrics
        .filter(F.col("customer_state").isNotNull())
        .groupBy("customer_state")
        .agg(F.countDistinct("customer_unique_id").alias("customer_count"))
    )

    seller_by_state = (
        sellers
        .filter(F.col("seller_state").isNotNull())
        .groupBy("seller_state")
        .agg(F.countDistinct("seller_id").alias("seller_count"))
    )

    return cust_by_state, seller_by_state
