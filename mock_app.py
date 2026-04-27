from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from data_models import (
    ASSIGNMENT_VIEW_COLUMNS,
    CAREER_VIEW_COLUMNS,
    GROWTH_VIEW_COLUMNS,
    PROJECT_VIEW_COLUMNS,
    SKILL_VIEW_COLUMNS,
    TABLE_DEFINITIONS,
    TABLE_ORDER,
    build_assignment_view,
    build_career_view,
    build_growth_view,
    build_master_wiki_markdown,
    build_project_view,
    build_skill_view,
    ensure_database_state,
    export_artifacts,
    generate_assignments,
    generate_projects,
    get_database,
    import_career_view,
    import_growth_view,
    import_skill_view,
    load_dummy_database_into_session,
    load_dummy_table_into_session,
    load_dummy_view_into_session,
    save_table,
    table_payload,
)

PAGE_LABELS = {
    "home": "モック概要",
    "growth": "① 成長戦略の入力",
    "career": "② キャリア計画の入力",
    "skill": "③ スキルシートの入力",
    "project": "④ 仮想PJの出力",
    "assignment": "⑤ アサイン計画の出力",
    "shift_demo": "⑥ シフト最適化デモ",
    "master_guide": "マスタ管理ガイド",
}

MASTER_PAGE_LABELS = {
    "sales_strategy": "戦略マスタ",
    "fiscal_period": "時期マスタ",
    "sales_target": "売上目標マスタ",
    "skill": "スキルマスタ",
    "employee": "社員マスタ",
    "employee_skill": "社員保有スキルマスタ",
    "career_goal": "キャリア目標マスタ",
    "project": "案件マスタ",
    "project_required_skill": "案件必要スキルマスタ",
    "assignment": "アサインマスタ",
}

MASTER_PAGE_PATHS = {
    "sales_strategy": "pages/11_Sales_Strategy_Master.py",
    "fiscal_period": "pages/12_Fiscal_Period_Master.py",
    "sales_target": "pages/13_Sales_Target_Master.py",
    "skill": "pages/14_Skill_Master.py",
    "employee": "pages/15_Employee_Master.py",
    "employee_skill": "pages/16_Employee_Skill_Master.py",
    "career_goal": "pages/17_Career_Goal_Master.py",
    "project": "pages/18_Project_Master.py",
    "project_required_skill": "pages/19_Project_Required_Skill_Master.py",
    "assignment": "pages/20_Assignment_Master.py",
}

MASTER_GROUPS = {
    "基本マスタ": ["sales_strategy", "fiscal_period", "skill", "employee"],
    "業務マスタ": ["sales_target", "employee_skill", "career_goal", "project", "project_required_skill", "assignment"],
}


def ensure_session_state() -> dict[str, pd.DataFrame]:
    return ensure_database_state(st.session_state)


def render_sidebar() -> None:
    st.sidebar.subheader("モック")
    st.sidebar.page_link("app.py", label=PAGE_LABELS["home"], icon="🏠")
    st.sidebar.page_link("pages/1_Growth_Strategy_Input.py", label=PAGE_LABELS["growth"], icon="📈")
    st.sidebar.page_link("pages/2_Career_Plan_Input.py", label=PAGE_LABELS["career"], icon="🧭")
    st.sidebar.page_link("pages/3_Skill_Sheet_Input.py", label=PAGE_LABELS["skill"], icon="🛠️")
    st.sidebar.page_link("pages/4_Virtual_Projects_Output.py", label=PAGE_LABELS["project"], icon="📦")
    st.sidebar.page_link("pages/5_Assignment_Plan_Output.py", label=PAGE_LABELS["assignment"], icon="🤝")
    st.sidebar.subheader("(開発者用)マスタ管理")
    st.sidebar.page_link("pages/10_Master_Data_Guide.py", label=PAGE_LABELS["master_guide"], icon="🗂️")
    for group_name, table_names in MASTER_GROUPS.items():
        with st.sidebar.expander(group_name, expanded=False):
            for table_name in table_names:
                st.page_link(MASTER_PAGE_PATHS[table_name], label=MASTER_PAGE_LABELS[table_name], icon="🧾")
    st.sidebar.subheader("コア検証")
    st.sidebar.page_link("pages/6_Shift_Optimization_Demo.py", label=PAGE_LABELS["shift_demo"], icon="🧩")


def dataframe_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def _summary_text(df: pd.DataFrame, table_name: str) -> str:
    if df.empty:
        return f"{table_name}はまだ投入されていません。CSV投入またはダミーデータ生成を実行してください。"

    if table_name == "成長戦略":
        total = int(pd.to_numeric(df["お金"], errors="coerce").fillna(0).sum())
        peak = int(pd.to_numeric(df["お金"], errors="coerce").fillna(0).max())
        return f"成長戦略は {len(df)} 件で、合計売上目標は {total:,}、最大売上目標は {peak:,} です。"

    if table_name == "キャリア計画":
        employees = df["ID"].nunique()
        skills = ", ".join(df["スキル"].dropna().astype(str).unique()[:3])
        return f"キャリア計画は {len(df)} 件で、対象社員は {employees} 名です。主要スキルは {skills or '未設定'} です。"

    if table_name == "スキルシート":
        employees = df["ID"].nunique()
        avg_level = round(pd.to_numeric(df["スキルのLv"], errors="coerce").fillna(0).mean(), 1)
        return f"スキルシートは {len(df)} 件で、対象社員は {employees} 名、平均スキルLvは {avg_level} です。"

    if table_name == "仮想PJ":
        periods = df["時期"].nunique()
        return f"仮想PJは {len(df)} 件で、{periods} 期間にまたがる案件候補を保持しています。"

    assigned = df["ID"].nunique()
    return f"アサイン計画は {len(df)} 件で、割当対象社員は {assigned} 名です。"


def render_output_summary_and_charts(df: pd.DataFrame, summary_label: str) -> None:
    st.subheader("要約")
    st.write(_summary_text(df, summary_label))
    if df.empty:
        return

    st.subheader("グラフ")
    columns = st.columns(2)
    if "時期" in df.columns:
        period_counts = df.groupby("時期").size().reset_index(name="件数").set_index("時期")
        with columns[0]:
            st.caption("時期ごとの件数")
            st.bar_chart(period_counts)
    if "スキル" in df.columns:
        skill_counts = df.groupby("スキル").size().reset_index(name="件数").set_index("スキル")
        with columns[1]:
            st.caption("スキルごとの件数")
            st.bar_chart(skill_counts)


def _render_input_bi(view_df: pd.DataFrame, view_key: str) -> None:
    st.subheader("BI")
    if view_df.empty:
        st.info("BI表示対象のデータがありません。")
        return

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("行数", len(view_df))
    if view_key == "growth":
        with metric_cols[1]:
            st.metric("期間数", view_df["時期"].nunique())
        with metric_cols[2]:
            st.metric("売上目標合計", f"{int(pd.to_numeric(view_df['お金'], errors='coerce').fillna(0).sum()):,}")
        chart_cols = st.columns(2)
        with chart_cols[0]:
            by_period = view_df.groupby("時期", as_index=False)["お金"].sum().set_index("時期")
            st.caption("時期ごとの売上目標")
            st.bar_chart(by_period)
        with chart_cols[1]:
            st.caption("売上目標の分布")
            hist_df = pd.DataFrame({"売上目標": pd.to_numeric(view_df["お金"], errors="coerce").fillna(0)})
            st.bar_chart(hist_df)
        return

    with metric_cols[1]:
        st.metric("社員数", view_df["ID"].nunique())
    with metric_cols[2]:
        st.metric("スキル数", view_df["スキル"].nunique())

    chart_cols = st.columns(2)
    with chart_cols[0]:
        skill_counts = view_df.groupby("スキル").size().reset_index(name="件数").set_index("スキル")
        st.caption("スキルごとの件数")
        st.bar_chart(skill_counts)
    with chart_cols[1]:
        if "時期" in view_df.columns:
            period_counts = view_df.groupby("時期").size().reset_index(name="件数").set_index("時期")
            st.caption("時期ごとの件数")
            st.bar_chart(period_counts)
        else:
            level_counts = view_df.groupby("スキルのLv").size().reset_index(name="件数").set_index("スキルのLv")
            st.caption("レベルごとの件数")
            st.bar_chart(level_counts)


def _input_actions(uploaded_file, importer, view_key: str) -> None:
    action_cols = st.columns([1, 1, 2])
    with action_cols[0]:
        if st.button("CSVを反映", type="primary", use_container_width=True):
            if uploaded_file is None:
                st.warning("CSVファイルが未選択です。")
            else:
                importer(st.session_state, pd.read_csv(uploaded_file))
                st.success("CSVからデータを取り込みました。")
                st.rerun()
    with action_cols[1]:
        if st.button("このページのダミーデータ読込", use_container_width=True):
            load_dummy_view_into_session(st.session_state, view_key)
            st.success("このページで管理するダミーデータを読み込みました。")
            st.rerun()


def render_input_page(title: str, description: str, view_key: str) -> None:
    ensure_session_state()
    render_sidebar()
    st.title(title)
    st.caption(description)

    database = get_database(st.session_state)
    builders = {
        "growth": build_growth_view,
        "career": build_career_view,
        "skill": build_skill_view,
    }
    importers = {
        "growth": import_growth_view,
        "career": import_career_view,
        "skill": import_skill_view,
    }
    view_df = builders[view_key](database)
    st.subheader("データ投入")
    uploaded_file = st.file_uploader("CSVファイルを選択", type=["csv"], key=f"uploader_{view_key}")
    _input_actions(uploaded_file, importers[view_key], view_key)

    st.subheader("現在の表示")
    if view_df.empty:
        st.info("データ未投入です。CSVを読み込むか、このページのダミーデータ読込を実行してください。")
    else:
        st.dataframe(view_df, use_container_width=True, hide_index=True)
    _render_input_bi(view_df, view_key)


def render_project_output_page() -> None:
    ensure_session_state()
    render_sidebar()
    st.title(PAGE_LABELS["project"])
    st.caption("正規化テーブルをもとに仮想PJビューを JOIN して表示します。現状はモックのため、厳密な最適化計算ではなくヒューリスティックな疑似計算で結果を作成します。")

    database = get_database(st.session_state)
    action_cols = st.columns([1, 3])
    with action_cols[0]:
        if st.button("仮想PJを計算", type="primary", use_container_width=True):
            generate_projects(st.session_state)
            st.success("仮想PJを計算しました。")
            st.rerun()

    project_df = build_project_view(database)
    if project_df.empty:
        st.info("案件データがありません。売上目標を投入した上で計算してください。")
    else:
        st.subheader("仮想PJ一覧テーブル")
        st.dataframe(project_df, use_container_width=True, hide_index=True)
        render_output_summary_and_charts(project_df, "仮想PJ")
        st.download_button(
            label="仮想PJ一覧をCSVダウンロード",
            data=dataframe_to_csv(project_df),
            file_name="virtual_projects_view.csv",
            mime="text/csv",
        )


def render_assignment_output_page() -> None:
    ensure_session_state()
    render_sidebar()
    st.title(PAGE_LABELS["assignment"])
    st.caption("正規化テーブルをもとにアサインビューを JOIN して表示します。現状はモックのため、厳密な最適化計算ではなくルールベースの疑似計算で結果を作成します。")

    action_cols = st.columns([1, 3])
    with action_cols[0]:
        if st.button("アサインを計算", type="primary", use_container_width=True):
            generate_assignments(st.session_state)
            st.success("アサイン計画を計算しました。")
            st.rerun()

    database = get_database(st.session_state)
    assignment_df = build_assignment_view(database)
    if assignment_df.empty:
        st.info("アサインデータがありません。仮想PJ計算後にアサインを計算してください。")
    else:
        st.subheader("アサイン計画一覧テーブル")
        st.dataframe(assignment_df, use_container_width=True, hide_index=True)
        render_output_summary_and_charts(assignment_df, "アサイン計画")
        st.download_button(
            label="アサイン計画をCSVダウンロード",
            data=dataframe_to_csv(assignment_df),
            file_name="assignment_view.csv",
            mime="text/csv",
        )


def render_master_guide_page() -> None:
    ensure_session_state()
    render_sidebar()
    st.title(PAGE_LABELS["master_guide"])
    st.markdown(build_master_wiki_markdown())

    st.subheader("現在の件数")
    database = get_database(st.session_state)
    payload = pd.DataFrame(table_payload(database))
    st.dataframe(payload, use_container_width=True, hide_index=True)


def render_table_admin_page(table_name: str) -> None:
    ensure_session_state()
    render_sidebar()
    definition = TABLE_DEFINITIONS[table_name]
    database = get_database(st.session_state)

    st.title(MASTER_PAGE_LABELS[table_name])
    st.caption(definition.description)

    source_path = Path("data") / f"{table_name}.csv"
    st.write(f"ダミーデータ元: `{source_path}`")

    edited_df = st.data_editor(
        database[table_name],
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_{table_name}",
    )

    action_cols = st.columns([1, 1, 2])
    with action_cols[0]:
        if st.button("保存", type="primary", use_container_width=True):
            save_table(st.session_state, table_name, pd.DataFrame(edited_df))
            st.success("テーブルを保存しました。")
            st.rerun()
    with action_cols[1]:
        if st.button("ダミーデータ読込", use_container_width=True):
            load_dummy_table_into_session(st.session_state, table_name)
            st.success("このテーブルのダミーデータを読み込みました。")
            st.rerun()
    with action_cols[2]:
        st.download_button(
            label="現在テーブルをCSVダウンロード",
            data=dataframe_to_csv(database[table_name]),
            file_name=f"{table_name}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def render_home_page() -> None:
    ensure_session_state()
    render_sidebar()
    st.title(PAGE_LABELS["home"])
    st.caption("Pandera で検証する正規化データモデルを中核にし、表示用DataFrameは JOIN ビューとして扱うモックです。")

    st.subheader("このサービスで管理するデータ")
    database = get_database(st.session_state)
    payload = pd.DataFrame(table_payload(database))
    st.dataframe(payload, use_container_width=True, hide_index=True)

    st.subheader("画面の流れ")
    st.markdown(
        """
1. `① 成長戦略の入力` で売上目標ビューを投入する
2. `② キャリア計画の入力` でキャリア目標ビューを投入する
3. `③ スキルシートの入力` で社員保有スキルビューを投入する
4. `マスタ管理` で正規化済みテーブルを直接調整する
5. `④ 仮想PJの出力` と `⑤ アサイン計画の出力` で JOIN ビューを確認する
"""
    )

    button_cols = st.columns([1, 1, 2])
    with button_cols[0]:
        if st.button("ダミーデータ生成", type="primary", use_container_width=True):
            load_dummy_database_into_session(st.session_state)
            st.success("data/ 配下のダミーCSVを読み込みました。")
            st.rerun()
    with button_cols[1]:
        if st.button("ER図とデータを書き出す", use_container_width=True):
            written_paths = export_artifacts(st.session_state)
            st.success("出力を更新しました。")
            for path in written_paths:
                st.code(str(path))

    st.subheader("表示ビュー")
    view_tabs = st.tabs(["成長戦略", "キャリア計画", "スキルシート", "仮想PJ", "アサイン計画"])
    views = [
        build_growth_view(database),
        build_career_view(database),
        build_skill_view(database),
        build_project_view(database),
        build_assignment_view(database),
    ]
    for tab, df in zip(view_tabs, views, strict=True):
        with tab:
            if df.empty:
                st.info("まだデータがありません。")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
