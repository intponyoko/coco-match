import streamlit as st

from mock_app import PAGE_LABELS, render_home_page

st.set_page_config(page_title=PAGE_LABELS["home"], page_icon="🏠", layout="wide")

render_home_page()
