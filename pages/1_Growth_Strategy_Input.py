import streamlit as st

from mock_app import PAGE_LABELS, render_input_page

st.set_page_config(page_title=PAGE_LABELS["growth"], page_icon="📈", layout="wide")

render_input_page(
    title=PAGE_LABELS["growth"],
    description="売上目標ビューをCSVから取り込みます。列は「時期」「お金」で、`お金` は売上目標額として扱います。",
    view_key="growth",
)
