from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from mock_app import PAGE_LABELS, dataframe_to_csv, render_sidebar

try:
    from z3 import Bool, If, Not, Optimize, Or, Sum, is_true, sat
except ImportError:  # pragma: no cover - shown in the Streamlit UI.
    Bool = If = Not = Optimize = Or = Sum = is_true = sat = None


SHIFT_DEFINITIONS = [
    {"シフト": "早番", "必要人数": 4, "給与(円)": 15000},
    {"シフト": "日勤", "必要人数": 4, "給与(円)": 10000},
    {"シフト": "遅番", "必要人数": 4, "給与(円)": 10000},
]
SHIFT_NAMES = [shift["シフト"] for shift in SHIFT_DEFINITIONS]
SHIFT_PAY = {shift["シフト"]: int(shift["給与(円)"]) for shift in SHIFT_DEFINITIONS}
SHIFT_REQUIRED = {shift["シフト"]: int(shift["必要人数"]) for shift in SHIFT_DEFINITIONS}
EMPLOYEES = list(range(1, 31))
EARNING_EMPLOYEES = set(range(11, 21))
LATE_AVOIDING_EMPLOYEES = set(range(21, 31))
OFF_SHIFT = "休み"


@dataclass(frozen=True)
class ShiftPlan:
    rank: int
    objective_value: int
    earning_group_salary: int
    late_avoiding_late_count: int
    total_salary: int
    assignment_df: pd.DataFrame
    employee_df: pd.DataFrame
    daily_df: pd.DataFrame


def employee_group(employee_no: int) -> str:
    if employee_no in EARNING_EMPLOYEES:
        return "稼得重視"
    if employee_no in LATE_AVOIDING_EMPLOYEES:
        return "遅番回避"
    return "中立"


def employee_feature(employee_no: int) -> str:
    if employee_no in EARNING_EMPLOYEES:
        return "ハードワークでもいいので、たくさん稼ぎたい"
    if employee_no in LATE_AVOIDING_EMPLOYEES:
        return "なるべく遅番に入りたくない"
    return "特徴がなく、あまりシフトに対して文句を言わない"


def build_employee_master() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "従業員No": employee_no,
                "グループ": employee_group(employee_no),
                "特徴": employee_feature(employee_no),
            }
            for employee_no in EMPLOYEES
        ]
    )


def build_employee_group_summary(employee_df: pd.DataFrame) -> pd.DataFrame:
    return (
        employee_df.groupby("グループ", as_index=False)
        .agg(人数=("従業員No", "count"), 特徴=("特徴", "first"))
        .sort_values("グループ")
    )


def bool_to_int(value) -> object:
    return If(value, 1, 0)


def has_valid_workload(schedule: list[str]) -> bool:
    work = [shift != OFF_SHIFT for shift in schedule]
    for start in range(0, max(len(schedule) - 6, 0)):
        if sum(work[start : start + 7]) > 6:
            return False
    for start in range(0, max(len(schedule) - 9, 0)):
        if sum(work[start : start + 10]) > 9:
            return False
    return True


def has_valid_late_pattern(schedule: list[str]) -> bool:
    late = [shift == "遅番" for shift in schedule]
    for start in range(0, max(len(schedule) - 2, 0)):
        if sum(late[start : start + 3]) > 2:
            return False
    if len(schedule) >= 2 and late[0] and not late[1]:
        return False
    for index in range(1, len(schedule) - 1):
        if late[index] and not (late[index - 1] or late[index + 1]):
            return False
    return True


def can_assign(schedule: list[str], day_index: int, shift_name: str) -> bool:
    if schedule[day_index] != OFF_SHIFT:
        return False
    candidate = schedule.copy()
    candidate[day_index] = shift_name
    return has_valid_workload(candidate)


def choose_employees_for_shift(
    schedules: dict[int, list[str]],
    day_indexes: list[int],
    shift_name: str,
    employee_order: list[int],
) -> list[int]:
    candidates = []
    for order_index, employee_no in enumerate(employee_order):
        if all(can_assign(schedules[employee_no], day_index, shift_name) for day_index in day_indexes):
            current_schedule = schedules[employee_no]
            candidates.append(
                (
                    sum(shift != OFF_SHIFT for shift in current_schedule),
                    sum(shift == shift_name for shift in current_schedule),
                    order_index,
                    employee_no,
                )
            )

    selected = [employee_no for _, _, _, employee_no in sorted(candidates)[: SHIFT_REQUIRED[shift_name]]]
    if len(selected) != SHIFT_REQUIRED[shift_name]:
        raise ValueError("勤務パターン候補を生成できませんでした。")
    return selected


def rotate(values: list[int], amount: int) -> list[int]:
    if not values:
        return values
    offset = amount % len(values)
    return values[offset:] + values[:offset]


def build_roster_template(day_count: int, variant: int) -> dict[int, tuple[str, ...]]:
    schedules = {employee_no: [OFF_SHIFT] * day_count for employee_no in EMPLOYEES}
    neutral_and_earning = list(range(1, 21))
    late_pool_variants = [
        neutral_and_earning,
        list(range(6, 21)) + list(range(1, 6)),
        list(range(11, 21)) + list(range(1, 11)),
        EMPLOYEES,
        list(range(1, 16)) + list(range(21, 31)) + list(range(16, 21)),
        list(range(11, 31)) + list(range(1, 11)),
    ]
    late_pool = rotate(late_pool_variants[variant % len(late_pool_variants)], variant * 3)

    for start_day in range(0, day_count, 2):
        day_indexes = [start_day]
        if start_day + 1 < day_count:
            day_indexes.append(start_day + 1)
        selected = choose_employees_for_shift(schedules, day_indexes, "遅番", rotate(late_pool, start_day * 2))
        for employee_no in selected:
            for day_index in day_indexes:
                schedules[employee_no][day_index] = "遅番"

    early_orders = [
        list(range(11, 21)) + list(range(1, 11)) + list(range(21, 31)),
        list(range(1, 21)) + list(range(21, 31)),
        list(range(11, 31)) + list(range(1, 11)),
    ]
    day_orders = [
        list(range(1, 11)) + list(range(11, 21)) + list(range(21, 31)),
        list(range(11, 21)) + list(range(21, 31)) + list(range(1, 11)),
        EMPLOYEES,
    ]

    for day_index in range(day_count):
        early_order = rotate(early_orders[variant % len(early_orders)], day_index * 2 + variant)
        day_order = rotate(day_orders[variant % len(day_orders)], day_index * 3 + variant)
        for shift_name, order in [("早番", early_order), ("日勤", day_order)]:
            selected = choose_employees_for_shift(schedules, [day_index], shift_name, order)
            for employee_no in selected:
                schedules[employee_no][day_index] = shift_name

    for employee_no, schedule in schedules.items():
        if not has_valid_workload(schedule) or not has_valid_late_pattern(schedule):
            raise ValueError(f"No.{employee_no} の勤務パターンが制約を満たしていません。")

    return {employee_no: tuple(schedule) for employee_no, schedule in schedules.items()}


def build_candidate_rosters(day_count: int, variant_count: int = 12) -> list[dict[int, tuple[str, ...]]]:
    rosters: list[dict[int, tuple[str, ...]]] = []
    for variant in range(variant_count):
        roster = build_roster_template(day_count, variant)
        if roster not in rosters:
            rosters.append(roster)
    return rosters


def roster_metrics(roster: dict[int, tuple[str, ...]]) -> tuple[int, int]:
    earning_group_salary = sum(
        SHIFT_PAY.get(shift_name, 0)
        for employee_no in EARNING_EMPLOYEES
        for shift_name in roster[employee_no]
    )
    late_avoiding_late_count = sum(
        shift_name == "遅番"
        for employee_no in LATE_AVOIDING_EMPLOYEES
        for shift_name in roster[employee_no]
    )
    return int(earning_group_salary), int(late_avoiding_late_count)


def build_optimizer(day_count: int, w1: int, w2: int):
    candidate_rosters = build_candidate_rosters(day_count)
    opt = Optimize()
    opt.set(timeout=10_000)
    variables = {roster_index: Bool(f"roster_{roster_index}") for roster_index in range(len(candidate_rosters))}
    opt.add(Sum([bool_to_int(variable) for variable in variables.values()]) == 1)

    earning_group_salary = Sum(
        [
            bool_to_int(variables[roster_index]) * roster_metrics(roster)[0]
            for roster_index, roster in enumerate(candidate_rosters)
        ]
    )
    late_avoiding_late_count = Sum(
        [
            bool_to_int(variables[roster_index]) * roster_metrics(roster)[1]
            for roster_index, roster in enumerate(candidate_rosters)
        ]
    )

    objective = w1 * earning_group_salary - w2 * late_avoiding_late_count
    opt.maximize(objective)
    return opt, variables, candidate_rosters


def extract_plan(
    rank: int,
    model,
    variables: dict[int, object],
    candidate_rosters: list[dict[int, tuple[str, ...]]],
    day_count: int,
    w1: int,
    w2: int,
) -> ShiftPlan:
    assignment_rows: list[dict[str, object]] = []
    daily_rows: list[dict[str, object]] = []
    employee_rows: list[dict[str, object]] = []

    selected_roster = candidate_rosters[0]
    for roster_index, variable in variables.items():
        if is_true(model.evaluate(variable, model_completion=True)):
            selected_roster = candidate_rosters[roster_index]
            break

    for day in range(1, day_count + 1):
        daily_row: dict[str, object] = {"日": day}
        for shift_name in SHIFT_NAMES:
            assigned = [
                employee_no
                for employee_no in EMPLOYEES
                if selected_roster[employee_no][day - 1] == shift_name
            ]
            daily_row[shift_name] = ", ".join([f"No.{employee_no}" for employee_no in assigned])
            for employee_no in assigned:
                assignment_rows.append(
                    {
                        "日": day,
                        "従業員No": employee_no,
                        "グループ": employee_group(employee_no),
                        "シフト": shift_name,
                        "給与(円)": SHIFT_PAY[shift_name],
                    }
                )
        daily_rows.append(daily_row)

    assignment_df = pd.DataFrame(assignment_rows)
    for employee_no in EMPLOYEES:
        employee_assignments = assignment_df[assignment_df["従業員No"] == employee_no]
        employee_rows.append(
            {
                "従業員No": employee_no,
                "グループ": employee_group(employee_no),
                "勤務日数": len(employee_assignments),
                "給与合計(円)": int(employee_assignments["給与(円)"].sum()),
                "遅番回数": int((employee_assignments["シフト"] == "遅番").sum()),
                "早番回数": int((employee_assignments["シフト"] == "早番").sum()),
                "日勤回数": int((employee_assignments["シフト"] == "日勤").sum()),
            }
        )

    employee_df = pd.DataFrame(employee_rows)
    earning_group_salary = int(employee_df[employee_df["グループ"] == "稼得重視"]["給与合計(円)"].sum())
    late_avoiding_late_count = int(employee_df[employee_df["グループ"] == "遅番回避"]["遅番回数"].sum())
    total_salary = int(employee_df["給与合計(円)"].sum())
    objective_value = w1 * earning_group_salary - w2 * late_avoiding_late_count

    return ShiftPlan(
        rank=rank,
        objective_value=objective_value,
        earning_group_salary=earning_group_salary,
        late_avoiding_late_count=late_avoiding_late_count,
        total_salary=total_salary,
        assignment_df=assignment_df,
        employee_df=employee_df,
        daily_df=pd.DataFrame(daily_rows),
    )


def add_blocking_constraint(opt, model, variables: dict[int, object]) -> None:
    differences = []
    for key, variable in variables.items():
        value = is_true(model.evaluate(variable, model_completion=True))
        differences.append(Not(variable) if value else variable)
    opt.add(Or(*differences))


def solve_top_plans(day_count: int, w1: int, w2: int, top_n: int = 3) -> tuple[list[ShiftPlan], str | None]:
    if Optimize is None:
        return [], "z3-solver がインストールされていません。`uv sync` を実行して依存関係を更新してください。"

    try:
        opt, variables, candidate_rosters = build_optimizer(day_count, w1, w2)
    except ValueError as exc:
        return [], str(exc)

    plans: list[ShiftPlan] = []

    for rank in range(1, top_n + 1):
        result = opt.check()
        if result != sat:
            break
        model = opt.model()
        plans.append(extract_plan(rank, model, variables, candidate_rosters, day_count, w1, w2))
        add_blocking_constraint(opt, model, variables)

    if not plans:
        return [], "条件を満たすシフト計画が見つかりませんでした。日数や制約を見直してください。"
    return plans, None


def render_plan(plan: ShiftPlan) -> None:
    metric_cols = st.columns(4)
    metric_cols[0].metric("目的値", f"{plan.objective_value:,}")
    metric_cols[1].metric("総給与", f"{plan.total_salary:,} 円")
    metric_cols[2].metric("No.11-20 給与", f"{plan.earning_group_salary:,} 円")
    metric_cols[3].metric("No.21-30 遅番", f"{plan.late_avoiding_late_count:,} 回")

    st.subheader("日別シフト表")
    st.dataframe(plan.daily_df, use_container_width=True, hide_index=True)

    st.subheader("従業員別サマリー")
    st.dataframe(plan.employee_df, use_container_width=True, hide_index=True)

    chart_cols = st.columns(3)
    chart_data = plan.employee_df.set_index("従業員No")
    with chart_cols[0]:
        st.caption("従業員別勤務日数")
        st.bar_chart(chart_data[["勤務日数"]])
    with chart_cols[1]:
        st.caption("従業員別給与")
        st.bar_chart(chart_data[["給与合計(円)"]])
    with chart_cols[2]:
        st.caption("従業員別遅番回数")
        st.bar_chart(chart_data[["遅番回数"]])

    st.download_button(
        label=f"計画{plan.rank}の割当明細をCSVダウンロード",
        data=dataframe_to_csv(plan.assignment_df),
        file_name=f"shift_plan_{plan.rank}.csv",
        mime="text/csv",
        key=f"download_shift_plan_{plan.rank}",
    )


st.set_page_config(page_title=PAGE_LABELS["shift_demo"], page_icon="🧩", layout="wide")
render_sidebar()

st.title(PAGE_LABELS["shift_demo"])
st.caption("Z3を使って、スーパーの早番・日勤・遅番に30人のパートタイム職員を割り当てます。デモとして最大14日分を扱います。")

control_cols = st.columns([1, 1, 1])
with control_cols[0]:
    day_count = st.number_input("対象日数", min_value=2, max_value=14, value=14, step=1)
with control_cols[1]:
    w1 = st.slider("w1: No.11-20の給与重み", min_value=1, max_value=10, value=1, step=1)
with control_cols[2]:
    w2 = st.slider("w2: No.21-30の遅番ペナルティ", min_value=1, max_value=100_000, value=1, step=1)

if int(day_count) % 2 == 1:
    st.info("対象日数が奇数のため、最終日の遅番は翌月継続扱いとしてペア制約の例外を認めます。")

st.subheader("入力データ")
input_cols = st.columns(2)
with input_cols[0]:
    st.caption("シフト概要")
    st.dataframe(pd.DataFrame(SHIFT_DEFINITIONS), use_container_width=True, hide_index=True)
with input_cols[1]:
    employee_master = build_employee_master()
    st.caption("従業員グループ")
    st.dataframe(build_employee_group_summary(employee_master), use_container_width=True, hide_index=True)

with st.expander("従業員マスタを表示"):
    st.dataframe(employee_master, use_container_width=True, hide_index=True)

st.subheader("制約と目的関数")
constraint_cols = st.columns(2)
with constraint_cols[0]:
    st.markdown(
        """
- 各日・各シフトに必要人数4人を割り当てる
- 1人が同日に複数シフトへ入らない
- 任意の連続7日間で勤務日は最大6日
- 10連勤以上は禁止
- 遅番は最大2連続
- 遅番は原則2日連続ペア、最終日は翌月継続扱いを許可
"""
    )
with constraint_cols[1]:
    st.code("maximize w1 * No.11-20の合計給与 - w2 * No.21-30の遅番割当数", language="text")

if "shift_optimization_result" not in st.session_state:
    st.session_state.shift_optimization_result = None

if st.button("シフト最適化を実行", type="primary"):
    with st.spinner("Z3で上位3計画を探索しています..."):
        st.session_state.shift_optimization_result = solve_top_plans(int(day_count), int(w1), int(w2), 3)

if st.session_state.shift_optimization_result is None:
    st.info("条件を調整して「シフト最適化を実行」を押すと、上位3つの計画を比較できます。")
    st.stop()

plans, error_message = st.session_state.shift_optimization_result

if error_message:
    st.warning(error_message)
else:
    st.subheader("上位3計画の比較")
    comparison_df = pd.DataFrame(
        [
            {
                "順位": plan.rank,
                "目的値": plan.objective_value,
                "No.11-20 給与(円)": plan.earning_group_salary,
                "No.21-30 遅番回数": plan.late_avoiding_late_count,
                "総給与(円)": plan.total_salary,
            }
            for plan in plans
        ]
    )
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    tabs = st.tabs([f"計画{plan.rank}" for plan in plans])
    for tab, plan in zip(tabs, plans, strict=True):
        with tab:
            render_plan(plan)
