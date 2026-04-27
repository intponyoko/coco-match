import streamlit as st

from mock_app import PAGE_LABELS, render_master_guide_page

st.set_page_config(page_title=PAGE_LABELS["master_guide"], page_icon="🗂️", layout="wide")

render_master_guide_page()
