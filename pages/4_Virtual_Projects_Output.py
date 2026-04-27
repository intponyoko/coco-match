import streamlit as st

from mock_app import PAGE_LABELS, render_project_output_page

st.set_page_config(page_title=PAGE_LABELS["project"], page_icon="📦", layout="wide")

render_project_output_page()
