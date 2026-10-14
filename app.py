"""
RetailScope — Customer Purchase Intelligence
Main Streamlit application entry point with modern navigation.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from src.ui_utils import _inject_css, render_sidebar_brand, render_sidebar_system_info

# Global page configuration
st.set_page_config(
    page_title="RetailScope — Customer Purchase Intelligence",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

_inject_css()

# Supported modern Streamlit Navigation API (Replaces confusing 'app' sidebar entry)
pages = [
    st.Page("pages/1_Business_Overview.py", title="Business Overview", icon="📊", default=True),
    st.Page("pages/2_Sales_Trends.py", title="Sales & Purchase Trends", icon="📈"),
    st.Page("pages/3_Customer_Analytics.py", title="Customer Analytics & RFM", icon="👥"),
    st.Page("pages/4_Product_Analytics.py", title="Product & Category Analytics", icon="🏷️"),
    st.Page("pages/5_Geographic_Analytics.py", title="Geographic Analytics", icon="🗺️"),
    st.Page("pages/6_Orders_Payments_Reviews.py", title="Orders, Payments & Reviews", icon="🛒"),
    st.Page("pages/7_Business_Insights.py", title="Business Insights", icon="💡"),
]

pg = st.navigation(pages)
pg.run()
