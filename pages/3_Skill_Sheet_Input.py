import streamlit as st

from mock_app import PAGE_LABELS, render_input_page

st.set_page_config(page_title=PAGE_LABELS["skill"], page_icon="🛠️", layout="wide")

render_input_page(
    title=PAGE_LABELS["skill"],
    description="社員保有スキルビューをCSVから取り込みます。列は「ID」「スキル」「スキルのLv」です。",
    view_key="skill",
)
