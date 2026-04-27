import streamlit as st

from mock_app import render_table_admin_page

st.set_page_config(page_title="時期マスタ", page_icon="🧾", layout="wide")

render_table_admin_page("fiscal_period")
