import streamlit as st

from mock_app import PAGE_LABELS, render_input_page

st.set_page_config(page_title=PAGE_LABELS["career"], page_icon="🧭", layout="wide")

render_input_page(
    title=PAGE_LABELS["career"],
    description="キャリア目標ビューをCSVから取り込みます。列は「ID」「時期」「スキル」「スキルのLv」です。",
    view_key="career",
)
