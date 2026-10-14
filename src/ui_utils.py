"""
Shared display utilities and design system for RetailScope Streamlit pages.

Handles:
- Professional light-mode UI/UX design system with high contrast
- Spark / Parquet caching and data loading
- Chart styling and unified Plotly theme
- High-contrast KPI cards, headers, and badges
- Category & product label formatting
"""

import os
import sys
import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Add project root so src imports work when running from pages/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Design System Color Palette (Strictly adheres to design requirements)
# ---------------------------------------------------------------------------
PALETTE = {
    "bg": "#F8FAFC",              # Main background (Slate 50)
    "card": "#FFFFFF",            # Main content card background
    "text_primary": "#0F172A",     # Primary text (Slate 900)
    "text_secondary": "#64748B",   # Secondary text (Slate 500)
    "text_muted": "#94A3B8",       # Muted text (Slate 400)
    "primary": "#2563EB",          # Primary accent (Blue 600)
    "secondary": "#0D9488",        # Secondary accent (Teal 600)
    "border": "#E2E8F0",           # Border color (Slate 200)
    "sidebar_bg": "#111827",       # Sidebar background (Gray 900)
    "sidebar_text": "#F8FAFC",     # Sidebar text (Slate 50)
    "success": "#10B981",          # Positive / success (Emerald 500)
    "warning": "#F59E0B",          # Warning (Amber 500)
    "danger": "#EF4444",           # Danger / negative (Red 500)
}

# Cohesive, high-contrast Plotly sequence
PLOTLY_COLORS = [
    "#2563EB",  # Blue
    "#0D9488",  # Teal
    "#F59E0B",  # Amber
    "#EF4444",  # Red
    "#8B5CF6",  # Purple
    "#06B6D4",  # Cyan
    "#10B981",  # Emerald
    "#EC4899",  # Pink
    "#F97316",  # Orange
    "#6366F1",  # Indigo
]

# Common Portuguese-to-English polished category title map
CATEGORY_PRETTY_MAP = {
    "health_beauty": "Health & Beauty",
    "computers_accessories": "Computers & Accessories",
    "bed_bath_table": "Bed, Bath & Table",
    "sports_leisure": "Sports & Leisure",
    "furniture_decor": "Furniture & Decor",
    "watches_gifts": "Watches & Gifts",
    "housewares": "Housewares",
    "telephony": "Telephony",
    "auto": "Auto & Automotive",
    "cool_stuff": "Cool Stuff",
    "garden_tools": "Garden Tools",
    "toys": "Toys & Games",
    "baby": "Baby Products",
    "stationery": "Stationery & Office",
    "perfumery": "Perfumery",
    "fashion_bags_accessories": "Fashion Bags & Accessories",
    "small_appliances": "Small Appliances",
    "musical_instruments": "Musical Instruments",
    "electronics": "Electronics",
    "home_appliances": "Home Appliances",
    "home_appliances_2": "Home Appliances 2",
    "pet_shop": "Pet Shop",
    "luggage_accessories": "Luggage & Accessories",
    "office_furniture": "Office Furniture",
    "construction_tools_construction": "Construction Tools",
    "drinks": "Drinks & Beverages",
    "food_drink": "Food & Drink",
    "food": "Food",
    "tablets_printing_image": "Tablets & Printing",
    "fixed_telephony": "Fixed Telephony",
    "air_conditioning": "Air Conditioning",
    "audio": "Audio Equipment",
    "cine_photo": "Cinema & Photo",
    "consoles_games": "Consoles & Games",
    "costruction_tools_tools": "Tools",
}


def format_category_name(cat: str) -> str:
    """Format category name from snake_case to readable Title Case."""
    if not cat or pd.isna(cat) or cat == "Unknown":
        return "Uncategorized"
    clean = str(cat).strip().lower()
    if clean in CATEGORY_PRETTY_MAP:
        return CATEGORY_PRETTY_MAP[clean]
    return clean.replace("_", " ").title()


def format_product_label(product_id: str, category: str = None, short_len: int = 7) -> str:
    """
    Format product ID into a transparent, honest, readable label:
    e.g. 'Product 6cd53… (Health & Beauty)'.
    """
    if not product_id or pd.isna(product_id):
        return "Unknown Product"
    pid_str = str(product_id).strip()
    short_id = pid_str[:short_len]
    base = f"Product {short_id}…"
    if category and not pd.isna(category) and category != "Unknown":
        cat_pretty = format_category_name(category)
        return f"{base} ({cat_pretty})"
    return base


# ---------------------------------------------------------------------------
# Spark & Data Loading (Cached at Streamlit Session / Resource Level)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Starting PySpark Big Data Engine…")
def get_spark():
    from src.spark_session import get_spark_session
    return get_spark_session()


@st.cache_data(show_spinner="Loading analytical order metrics…", ttl=3600)
def load_order_metrics(_spark):
    from src.data_loader import load_parquet
    return load_parquet(_spark, "order_metrics").toPandas()


@st.cache_data(show_spinner="Loading customer RFM segments…", ttl=3600)
def load_customer_rfm(_spark):
    from src.data_loader import load_parquet
    return load_parquet(_spark, "customer_rfm").toPandas()


@st.cache_data(show_spinner="Loading item-level product data…", ttl=3600)
def load_item_data(_spark):
    from src.data_loader import load_parquet
    return load_parquet(_spark, "item_data").toPandas()


@st.cache_data(show_spinner="Loading payment transactions…", ttl=3600)
def load_payments(_spark):
    from src.data_loader import load_parquet
    return load_parquet(_spark, "payments_clean").toPandas()


@st.cache_data(show_spinner="Loading seller distribution data…", ttl=3600)
def load_sellers(_spark):
    from src.data_loader import load_parquet
    return load_parquet(_spark, "sellers_clean").toPandas()


@st.cache_data(show_spinner="Loading customer review records…", ttl=3600)
def load_reviews(_spark):
    from src.data_loader import load_parquet
    return load_parquet(_spark, "reviews_clean").toPandas()


def check_processed_data():
    """Return True if processed Parquet data exists."""
    from src.data_loader import processed_data_exists
    return processed_data_exists()


# ---------------------------------------------------------------------------
# Global CSS & High-Contrast Design System
# ---------------------------------------------------------------------------

def _inject_css():
    st.markdown(
        """
        <style>
        /* Base Page Background & Global Typography */
        [data-testid="stAppViewContainer"] {
            background-color: #F8FAFC !important;
            color: #0F172A !important;
        }

        /* Enforce Dark High-Contrast Text for Headings */
        h1, h2, h3, h4, h5, h6 {
            color: #0F172A !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }

        /* Enforce Clear High-Contrast Text for Body & Paragraphs */
        p, span, div, li, td, th {
            color: #334155;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        /* Streamlit Native Markdown Text */
        .stMarkdown p {
            color: #334155 !important;
            font-size: 0.95rem;
            line-height: 1.55;
        }

        /* Sidebar Styling (High Contrast Dark Slate) */
        [data-testid="stSidebar"] {
            background-color: #111827 !important;
            border-right: 1px solid #1F2937 !important;
        }
        [data-testid="stSidebar"] * {
            color: #F8FAFC !important;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #93C5FD !important;
            font-size: 0.85rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            margin-top: 14px !important;
            margin-bottom: 8px !important;
        }
        [data-testid="stSidebar"] .stSelectbox label,
        [data-testid="stSidebar"] .stMultiSelect label,
        [data-testid="stSidebar"] .stDateInput label,
        [data-testid="stSidebar"] .stRadio label,
        [data-testid="stSidebar"] .stSlider label {
            color: #E2E8F0 !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
            color: #CBD5E1 !important;
            font-weight: 500 !important;
            border-radius: 6px !important;
            padding: 6px 12px !important;
            transition: all 0.15s ease !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {
            background-color: rgba(255, 255, 255, 0.08) !important;
            color: #FFFFFF !important;
        }

        /* Premium KPI Card System */
        .metric-card {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
            border: 1px solid #E2E8F0;
            border-left: 4px solid #2563EB;
            margin-bottom: 14px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
        }
        .metric-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 6px;
        }
        .metric-label {
            font-size: 0.74rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #64748B;
        }
        .metric-icon {
            font-size: 1.1rem;
            opacity: 0.85;
        }
        .metric-value {
            font-size: 1.85rem;
            font-weight: 800;
            color: #0F172A;
            line-height: 1.15;
            letter-spacing: -0.02em;
        }
        .metric-delta {
            font-size: 0.78rem;
            color: #64748B;
            margin-top: 5px;
            font-weight: 500;
        }

        /* Section Headers with Subtle Clean Accent */
        .section-header {
            font-size: 1.08rem;
            font-weight: 700;
            color: #0F172A;
            padding-bottom: 8px;
            border-bottom: 1.5px solid #E2E8F0;
            margin-top: 24px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Page Header Banner */
        .page-header-container {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 22px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }
        .page-header-title {
            font-size: 1.65rem;
            font-weight: 800;
            color: #0F172A;
            line-height: 1.2;
            letter-spacing: -0.02em;
        }
        .page-header-subtitle {
            font-size: 0.90rem;
            color: #64748B;
            margin-top: 4px;
        }
        .page-header-meta {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .badge-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 9999px;
            background: #F1F5F9;
            color: #334155;
            border: 1px solid #E2E8F0;
        }
        .badge-pill-success {
            background: #ECFDF5;
            color: #065F46;
            border-color: #A7F3D0;
        }
        .badge-pill-primary {
            background: #EFF6FF;
            color: #1E40AF;
            border-color: #BFDBFE;
        }

        /* Insight Card Styling */
        .insight-card {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 18px 22px;
            border: 1px solid #E2E8F0;
            border-top: 3px solid #2563EB;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
            margin-bottom: 14px;
            height: 100%;
        }
        .insight-category {
            font-size: 0.70rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color: #2563EB;
        }
        .insight-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #0F172A;
            margin: 4px 0 3px;
        }
        .insight-value {
            font-size: 1.35rem;
            font-weight: 800;
            color: #0F172A;
            letter-spacing: -0.01em;
            margin-bottom: 4px;
        }
        .insight-context {
            font-size: 0.82rem;
            color: #0D9488;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .insight-interpretation {
            font-size: 0.85rem;
            color: #475569;
            line-height: 1.5;
            border-top: 1px solid #F1F5F9;
            padding-top: 8px;
            margin-top: 6px;
        }

        /* Data Source / Footer Badge */
        .data-source-footer {
            font-size: 0.75rem;
            color: #94A3B8;
            text-align: right;
            padding: 14px 0 6px 0;
            border-top: 1px solid #E2E8F0;
            margin-top: 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Dataframe Table Polish */
        [data-testid="stDataFrame"] {
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #E2E8F0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar & Brand Header
# ---------------------------------------------------------------------------

def render_sidebar_brand():
    """Render top brand identity in the sidebar."""
    st.sidebar.markdown(
        """
        <div style="padding: 10px 4px 18px 4px; border-bottom: 1px solid #1F2937; margin-bottom: 14px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.9rem; line-height: 1;">🔭</span>
                <div>
                    <div style="font-size: 1.25rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.02em;">RetailScope</div>
                    <div style="font-size: 0.72rem; color: #94A3B8; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;">Customer Purchase Intelligence</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_system_info():
    """Display persistent system and Big Data pipeline status in the sidebar."""
    from src.spark_session import get_storage_mode
    mode = get_storage_mode()
    is_hive = "Hive" in mode
    mode_color = "#34D399" if is_hive else "#60A5FA"
    mode_badge = "🟢 Apache Hive" if is_hive else "🔵 Local Parquet"

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"""
        <div style="margin-top: 16px; padding: 14px 16px; background: rgba(255,255,255,0.04); border-radius: 10px; border: 1px solid rgba(255,255,255,0.08); font-size: 0.78rem; line-height: 1.6;">
            <div style="font-weight: 700; color: #93C5FD; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;">
                ⚡ Big Data Architecture
            </div>
            <div><b>Engine:</b> PySpark 4.2.0 (local[*])</div>
            <div><b>Storage:</b> <span style="color: {mode_color}; font-weight: 600;">{mode}</span></div>
            <div><b>Active Mode:</b> {mode_badge}</div>
            <div><b>Dataset:</b> Brazilian E-Commerce (Olist)</div>
            <div><b>Currency:</b> Brazilian Real (R$)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page Configuration & Components
# ---------------------------------------------------------------------------

def configure_page(title: str, icon: str = "📊"):
    try:
        st.set_page_config(
            page_title=f"{title} — RetailScope",
            page_icon=icon,
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass
    _inject_css()
    render_sidebar_brand()
    render_sidebar_system_info()


def render_page_header(
    title: str,
    subtitle: str,
    icon: str = "📊",
    date_range: tuple = None,
    badge_text: str = "Olist Real Transaction Data",
):
    """Render a unified, clean, professional page header banner."""
    date_pill = ""
    if date_range and date_range[0] and date_range[1]:
        start_str = date_range[0].strftime("%b %Y") if hasattr(date_range[0], "strftime") else str(date_range[0])
        end_str = date_range[1].strftime("%b %Y") if hasattr(date_range[1], "strftime") else str(date_range[1])
        date_pill = f'<div class="badge-pill badge-pill-primary">📅 {start_str} – {end_str}</div>'

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    st.markdown(
        f"""
        <div class="page-header-container">
            <div>
                <div class="page-header-title">{icon} {title}</div>
                <div class="page-header-subtitle">{subtitle}</div>
            </div>
            <div class="page-header-meta">
                {date_pill}
                <div class="badge-pill badge-pill-success">✓ {badge_text}</div>
                <div class="badge-pill">⏱ Freshness: {now_str}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, delta: str = "", color: str = "#2563EB", icon: str = "📈"):
    """Render an executive KPI card with high contrast."""
    st.markdown(
        f"""
        <div class="metric-card" style="border-left-color: {color};">
            <div class="metric-header">
                <span class="metric-label">{label}</span>
                <span class="metric-icon">{icon}</span>
            </div>
            <div class="metric-value">{value}</div>
            {"<div class='metric-delta'>" + delta + "</div>" if delta else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def insight_card(insight: dict):
    """Render a structured insight card with real measured context."""
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-category">{insight.get('category','')}</div>
            <div class="insight-title">{insight.get('title','')}</div>
            <div class="insight-value">{insight.get('value','')}</div>
            <div class="insight-context">{insight.get('context','')}</div>
            <div class="insight-interpretation">{insight.get('interpretation','')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(text: str, icon: str = "🔹"):
    st.markdown(f'<div class="section-header">{icon} {text}</div>', unsafe_allow_html=True)


def data_source_badge():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
        <div class="data-source-footer">
            <span>📦 Source: <b>Olist Brazilian E-Commerce Public Dataset</b> (100k Orders, 2016–2018)</span>
            <span>⚡ Big Data Pipeline: <b>PySpark 4.2.0</b> · Last Synchronized: <b>{now}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Plotly Unified Theme (Light-Mode, High Contrast, Crisp Typography)
# ---------------------------------------------------------------------------

def apply_chart_theme(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    """Apply an executive, readable Plotly theme with high-contrast text and labels."""
    fig.update_layout(
        template="plotly_white",
        title=dict(
            text=f"<b>{title}</b>" if title else "",
            font=dict(size=14, color="#0F172A", family="-apple-system, BlinkMacSystemFont, sans-serif"),
            x=0.01,
            y=0.96,
        ),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(
            family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            size=12,
            color="#334155",
        ),
        height=height,
        margin=dict(l=30, r=20, t=55 if title else 25, b=35),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.85)",
            font=dict(size=11, color="#334155"),
        ),
        hoverlabel=dict(
            bgcolor="#0F172A",
            font_size=12,
            font_family="-apple-system, BlinkMacSystemFont, sans-serif",
            font_color="#FFFFFF",
            bordercolor="#334155",
        ),
        colorway=PLOTLY_COLORS,
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor="#CBD5E1",
        tickcolor="#CBD5E1",
        tickfont=dict(color="#334155", size=11),
        title_font=dict(color="#0F172A", size=12, family="sans-serif"),
    )
    fig.update_yaxes(
        gridcolor="#F1F5F9",
        linecolor="#CBD5E1",
        tickcolor="#CBD5E1",
        tickfont=dict(color="#334155", size=11),
        title_font=dict(color="#0F172A", size=12, family="sans-serif"),
    )
    return fig


def format_brl(value: float) -> str:
    """Format a number as Brazilian Real (R$)."""
    if value is None or pd.isna(value):
        return "R$ 0.00"
    return f"R$ {value:,.2f}"


def no_data_msg():
    st.info("ℹ️ No records match the selected filters. Please broaden your date range or filter criteria.")


# ---------------------------------------------------------------------------
# Filter Sidebar Helpers
# ---------------------------------------------------------------------------

def render_date_filters(df: pd.DataFrame, date_col: str = "purchase_date") -> tuple:
    """Render date range filters in sidebar. Returns (start_date, end_date)."""
    if date_col not in df.columns:
        return None, None

    df[date_col] = pd.to_datetime(df[date_col])
    min_date = df[date_col].min().date()
    max_date = df[date_col].max().date()

    st.sidebar.markdown("### 📅 Date Range Filter")
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        start = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
    with col_d2:
        end = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)
    return start, end


def filter_by_dates(df: pd.DataFrame, start, end, date_col: str = "purchase_date") -> pd.DataFrame:
    """Filter DataFrame by date range."""
    if start is None or end is None or date_col not in df.columns:
        return df
    df[date_col] = pd.to_datetime(df[date_col])
    return df[(df[date_col].dt.date >= start) & (df[date_col].dt.date <= end)]


def pipeline_not_run_error():
    st.error(
        "⚠️ **Processed data not found.**\n\n"
        "Please run the Big Data pipeline first to prepare the analytical Parquet tables:\n"
        "```bash\npython scripts/run_pipeline.py\n```"
    )
