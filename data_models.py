from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd
import pandera.pandas as pa
from pandera.typing import Series

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = ROOT_DIR / "docs"
EXPORT_DIR = ROOT_DIR / "exports" / "normalized_state"

DATABASE_SESSION_KEY = "normalized_database"
DATABASE_MESSAGE_KEY = "normalized_database_message"

GROWTH_VIEW_COLUMNS = ["時期", "お金"]
CAREER_VIEW_COLUMNS = ["ID", "時期", "スキル", "スキルのLv"]
SKILL_VIEW_COLUMNS = ["ID", "スキル", "スキルのLv"]
PROJECT_VIEW_COLUMNS = ["PJ ID", "時期", "お金", "スキル", "スキルのLv"]
ASSIGNMENT_VIEW_COLUMNS = ["ID", "PJ ID", "時期", "スキル", "スキルのLv"]


class SalesStrategyModel(pa.DataFrameModel):
    strategy_id: Series[int] = pa.Field(gt=0)
    strategy_code: Series[str]
    strategy_name: Series[str]
    valid_from: Series[str]
    valid_to: Series[str]

    class Config:
        strict = True


class FiscalPeriodModel(pa.DataFrameModel):
    period_id: Series[int] = pa.Field(gt=0)
    period_code: Series[str]
    period_start: Series[str]
    period_end: Series[str]

    class Config:
        strict = True


class SalesTargetModel(pa.DataFrameModel):
    sales_target_id: Series[int] = pa.Field(gt=0)
    strategy_id: Series[int] = pa.Field(gt=0)
    period_id: Series[int] = pa.Field(gt=0)
    target_amount: Series[int] = pa.Field(ge=0)

    class Config:
        strict = True


class SkillModel(pa.DataFrameModel):
    skill_id: Series[int] = pa.Field(gt=0)
    skill_code: Series[str]
    skill_name: Series[str]
    skill_category: Series[str]

    class Config:
        strict = True


class EmployeeModel(pa.DataFrameModel):
    employee_id: Series[int] = pa.Field(gt=0)
    employee_code: Series[str]
    employee_name: Series[str]
    department: Series[str]

    class Config:
        strict = True


class EmployeeSkillModel(pa.DataFrameModel):
    employee_skill_id: Series[int] = pa.Field(gt=0)
    employee_id: Series[int] = pa.Field(gt=0)
    skill_id: Series[int] = pa.Field(gt=0)
    skill_level: Series[int] = pa.Field(ge=1, le=5)

    class Config:
        strict = True


class CareerGoalModel(pa.DataFrameModel):
    career_goal_id: Series[int] = pa.Field(gt=0)
    employee_id: Series[int] = pa.Field(gt=0)
    period_id: Series[int] = pa.Field(gt=0)
    desired_skill_id: Series[int] = pa.Field(gt=0)
    target_skill_level: Series[int] = pa.Field(ge=1, le=5)

    class Config:
        strict = True


class ProjectModel(pa.DataFrameModel):
    project_id: Series[int] = pa.Field(gt=0)
    sales_target_id: Series[int] = pa.Field(gt=0)
    period_id: Series[int] = pa.Field(gt=0)
    project_code: Series[str]
    project_name: Series[str]
    project_status: Series[str]

    class Config:
        strict = True


class ProjectRequiredSkillModel(pa.DataFrameModel):
    project_required_skill_id: Series[int] = pa.Field(gt=0)
    project_id: Series[int] = pa.Field(gt=0)
    skill_id: Series[int] = pa.Field(gt=0)
    required_skill_level: Series[int] = pa.Field(ge=1, le=5)
    required_headcount: Series[int] = pa.Field(ge=1)

    class Config:
        strict = True


class AssignmentModel(pa.DataFrameModel):
    assignment_id: Series[int] = pa.Field(gt=0)
    project_id: Series[int] = pa.Field(gt=0)
    employee_id: Series[int] = pa.Field(gt=0)
    assignment_period_id: Series[int] = pa.Field(gt=0)
    assigned_skill_id: Series[int] = pa.Field(gt=0)
    allocation_ratio: Series[float] = pa.Field(gt=0)

    class Config:
        strict = True


@dataclass(frozen=True)
class TableDefinition:
    name: str
    label: str
    description: str
    role: str
    columns: list[str]
    schema_model: type[pa.DataFrameModel]
    natural_key: list[str]
    id_column: str


TABLE_DEFINITIONS: dict[str, TableDefinition] = {
    "sales_strategy": TableDefinition(
        name="sales_strategy",
        label="成長戦略",
        description="成長戦略のヘッダです。売上目標群を束ねます。",
        role="マスタ",
        columns=["strategy_id", "strategy_code", "strategy_name", "valid_from", "valid_to"],
        schema_model=SalesStrategyModel,
        natural_key=["strategy_code"],
        id_column="strategy_id",
    ),
    "fiscal_period": TableDefinition(
        name="fiscal_period",
        label="時期マスタ",
        description="四半期や月を統一管理します。",
        role="マスタ",
        columns=["period_id", "period_code", "period_start", "period_end"],
        schema_model=FiscalPeriodModel,
        natural_key=["period_code"],
        id_column="period_id",
    ),
    "sales_target": TableDefinition(
        name="sales_target",
        label="売上目標",
        description="成長戦略ごとの時期別売上目標です。",
        role="トラン",
        columns=["sales_target_id", "strategy_id", "period_id", "target_amount"],
        schema_model=SalesTargetModel,
        natural_key=["strategy_id", "period_id"],
        id_column="sales_target_id",
    ),
    "skill": TableDefinition(
        name="skill",
        label="スキルマスタ",
        description="スキル名とカテゴリを統一管理します。",
        role="マスタ",
        columns=["skill_id", "skill_code", "skill_name", "skill_category"],
        schema_model=SkillModel,
        natural_key=["skill_name"],
        id_column="skill_id",
    ),
    "employee": TableDefinition(
        name="employee",
        label="社員マスタ",
        description="社員コードと所属を管理します。",
        role="マスタ",
        columns=["employee_id", "employee_code", "employee_name", "department"],
        schema_model=EmployeeModel,
        natural_key=["employee_code"],
        id_column="employee_id",
    ),
    "employee_skill": TableDefinition(
        name="employee_skill",
        label="社員保有スキル",
        description="社員が現在持つスキルとレベルを管理します。",
        role="トラン",
        columns=["employee_skill_id", "employee_id", "skill_id", "skill_level"],
        schema_model=EmployeeSkillModel,
        natural_key=["employee_id", "skill_id"],
        id_column="employee_skill_id",
    ),
    "career_goal": TableDefinition(
        name="career_goal",
        label="キャリア目標",
        description="社員が将来目指すスキルとレベルを管理します。",
        role="トラン",
        columns=["career_goal_id", "employee_id", "period_id", "desired_skill_id", "target_skill_level"],
        schema_model=CareerGoalModel,
        natural_key=["employee_id", "period_id", "desired_skill_id"],
        id_column="career_goal_id",
    ),
    "project": TableDefinition(
        name="project",
        label="案件ヘッダ",
        description="売上目標から導かれた仮想PJを管理します。",
        role="トラン",
        columns=["project_id", "sales_target_id", "period_id", "project_code", "project_name", "project_status"],
        schema_model=ProjectModel,
        natural_key=["project_code"],
        id_column="project_id",
    ),
    "project_required_skill": TableDefinition(
        name="project_required_skill",
        label="案件必要スキル",
        description="案件ごとの要求スキルと必要人数を管理します。",
        role="トラン",
        columns=["project_required_skill_id", "project_id", "skill_id", "required_skill_level", "required_headcount"],
        schema_model=ProjectRequiredSkillModel,
        natural_key=["project_id", "skill_id"],
        id_column="project_required_skill_id",
    ),
    "assignment": TableDefinition(
        name="assignment",
        label="アサイン",
        description="案件と社員の割当結果を管理します。",
        role="トラン",
        columns=["assignment_id", "project_id", "employee_id", "assignment_period_id", "assigned_skill_id", "allocation_ratio"],
        schema_model=AssignmentModel,
        natural_key=["project_id", "employee_id", "assigned_skill_id"],
        id_column="assignment_id",
    ),
}


TABLE_ORDER = list(TABLE_DEFINITIONS.keys())

VIEW_DUMMY_TABLES = {
    "growth": ["sales_strategy", "fiscal_period", "sales_target"],
    "career": ["employee", "fiscal_period", "skill", "career_goal"],
    "skill": ["employee", "skill", "employee_skill"],
}


def empty_table(table_name: str) -> pd.DataFrame:
    definition = TABLE_DEFINITIONS[table_name]
    return pd.DataFrame(columns=definition.columns)


def empty_database() -> dict[str, pd.DataFrame]:
    return {table_name: empty_table(table_name) for table_name in TABLE_ORDER}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _to_int(value: Any, default: int = 0) -> int:
    text = _stringify(value)
    if not text:
        return default
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    text = _stringify(value)
    if not text:
        return default
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return default


def _clean_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    cleaned = df.copy()
    cleaned = cleaned.fillna("")
    row_mask = cleaned.apply(lambda row: any(_stringify(value) for value in row.values), axis=1)
    return cleaned[row_mask].reset_index(drop=True)


def _coerce_table(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    definition = TABLE_DEFINITIONS[table_name]
    normalized = df.copy()
    for column in definition.columns:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = _clean_rows(normalized[definition.columns])

    if table_name in {"sales_strategy", "fiscal_period", "skill", "employee"}:
        int_columns = [definition.id_column]
        for column in int_columns:
            normalized[column] = normalized[column].map(lambda value: _to_int(value, 0))
        for column in [col for col in definition.columns if col not in int_columns]:
            normalized[column] = normalized[column].map(_stringify)
    elif table_name == "project":
        int_columns = ["project_id", "sales_target_id", "period_id"]
        for column in int_columns:
            normalized[column] = normalized[column].map(lambda value: _to_int(value, 0))
        for column in [col for col in definition.columns if col not in int_columns]:
            normalized[column] = normalized[column].map(_stringify)
    elif table_name in {"sales_target", "employee_skill", "career_goal", "project_required_skill"}:
        for column in definition.columns:
            if column.endswith("_id") or column.endswith("_level") or column in {"required_headcount", "target_amount"}:
                normalized[column] = normalized[column].map(lambda value: _to_int(value, 0))
    elif table_name == "assignment":
        for column in definition.columns:
            if column == "allocation_ratio":
                normalized[column] = normalized[column].map(lambda value: _to_float(value, 0.0))
            else:
                normalized[column] = normalized[column].map(lambda value: _to_int(value, 0))
    return normalized


def validate_table(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    definition = TABLE_DEFINITIONS[table_name]
    normalized = _coerce_table(table_name, df)
    if normalized.empty:
        return empty_table(table_name)
    return definition.schema_model.to_schema().validate(normalized, lazy=True)


def validate_database(database: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    validated = {}
    for table_name in TABLE_ORDER:
        validated[table_name] = validate_table(table_name, pd.DataFrame(database.get(table_name, empty_table(table_name))))
    return validated


def ensure_database_state(session_state: Any) -> dict[str, pd.DataFrame]:
    if DATABASE_SESSION_KEY not in session_state:
        session_state[DATABASE_SESSION_KEY] = empty_database()
    session_state[DATABASE_SESSION_KEY] = validate_database(session_state[DATABASE_SESSION_KEY])
    return session_state[DATABASE_SESSION_KEY]


def get_database(session_state: Any) -> dict[str, pd.DataFrame]:
    return ensure_database_state(session_state)


def set_database(session_state: Any, database: dict[str, pd.DataFrame]) -> None:
    session_state[DATABASE_SESSION_KEY] = validate_database(database)


def next_id(df: pd.DataFrame, id_column: str) -> int:
    if df.empty:
        return 1
    return int(df[id_column].max()) + 1


def infer_period_dates(period_code: str) -> tuple[str, str]:
    quarter_match = re.fullmatch(r"(\d{4})-Q([1-4])", period_code)
    if quarter_match:
        year = int(quarter_match.group(1))
        quarter = int(quarter_match.group(2))
        start_month = (quarter - 1) * 3 + 1
        start = pd.Timestamp(year=year, month=start_month, day=1)
        end = start + pd.offsets.QuarterEnd()
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    month_match = re.fullmatch(r"(\d{4})-(\d{2})", period_code)
    if month_match:
        year = int(month_match.group(1))
        month = int(month_match.group(2))
        start = pd.Timestamp(year=year, month=month, day=1)
        end = start + pd.offsets.MonthEnd()
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    return "2026-01-01", "2026-12-31"


def _upsert_periods(database: dict[str, pd.DataFrame], period_codes: list[str]) -> dict[str, int]:
    periods = database["fiscal_period"].copy()
    mapping = {
        _stringify(row["period_code"]): int(row["period_id"])
        for _, row in periods.iterrows()
    }
    for period_code in period_codes:
        code = _stringify(period_code)
        if not code or code in mapping:
            continue
        start, end = infer_period_dates(code)
        new_id = next_id(periods, "period_id")
        periods = pd.concat(
            [
                periods,
                pd.DataFrame(
                    [
                        {
                            "period_id": new_id,
                            "period_code": code,
                            "period_start": start,
                            "period_end": end,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        mapping[code] = new_id
    database["fiscal_period"] = validate_table("fiscal_period", periods)
    return mapping


def _upsert_employees(database: dict[str, pd.DataFrame], employee_codes: list[str]) -> dict[str, int]:
    employees = database["employee"].copy()
    mapping = {
        _stringify(row["employee_code"]): int(row["employee_id"])
        for _, row in employees.iterrows()
    }
    for employee_code in employee_codes:
        code = _stringify(employee_code)
        if not code or code in mapping:
            continue
        new_id = next_id(employees, "employee_id")
        employees = pd.concat(
            [
                employees,
                pd.DataFrame(
                    [
                        {
                            "employee_id": new_id,
                            "employee_code": code,
                            "employee_name": code,
                            "department": "未設定",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        mapping[code] = new_id
    database["employee"] = validate_table("employee", employees)
    return mapping


def _skill_code(skill_name: str, skill_id: int) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", "_", _stringify(skill_name)).strip("_").upper()
    if compact:
        return compact
    return f"SKILL_{skill_id:03d}"


def _upsert_skills(database: dict[str, pd.DataFrame], skill_names: list[str]) -> dict[str, int]:
    skills = database["skill"].copy()
    mapping = {
        _stringify(row["skill_name"]): int(row["skill_id"])
        for _, row in skills.iterrows()
    }
    for skill_name in skill_names:
        name = _stringify(skill_name)
        if not name or name in mapping:
            continue
        new_id = next_id(skills, "skill_id")
        skills = pd.concat(
            [
                skills,
                pd.DataFrame(
                    [
                        {
                            "skill_id": new_id,
                            "skill_code": _skill_code(name, new_id),
                            "skill_name": name,
                            "skill_category": "未分類",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        mapping[name] = new_id
    database["skill"] = validate_table("skill", skills)
    return mapping


def ensure_default_strategy(database: dict[str, pd.DataFrame]) -> int:
    strategies = database["sales_strategy"].copy()
    if strategies.empty:
        strategies = pd.DataFrame(
            [
                {
                    "strategy_id": 1,
                    "strategy_code": "STRATEGY-001",
                    "strategy_name": "標準成長戦略",
                    "valid_from": "2026-01-01",
                    "valid_to": "2028-12-31",
                }
            ]
        )
        database["sales_strategy"] = validate_table("sales_strategy", strategies)
        return 1
    database["sales_strategy"] = validate_table("sales_strategy", strategies)
    return int(database["sales_strategy"].sort_values("strategy_id").iloc[0]["strategy_id"])


def load_dummy_database() -> dict[str, pd.DataFrame]:
    database = {}
    for table_name in TABLE_ORDER:
        csv_path = DATA_DIR / f"{table_name}.csv"
        if csv_path.exists():
            database[table_name] = pd.read_csv(csv_path)
        else:
            database[table_name] = empty_table(table_name)
    return validate_database(database)


def load_dummy_database_into_session(session_state: Any) -> None:
    set_database(session_state, load_dummy_database())
    session_state[DATABASE_MESSAGE_KEY] = "data_loaded"


def load_dummy_view_into_session(session_state: Any, view_key: str) -> None:
    database = get_database(session_state).copy()
    dummy_database = load_dummy_database()
    for table_name in VIEW_DUMMY_TABLES[view_key]:
        database[table_name] = dummy_database[table_name].copy()
    set_database(session_state, database)
    session_state[DATABASE_MESSAGE_KEY] = f"{view_key}_data_loaded"


def load_dummy_table_into_session(session_state: Any, table_name: str) -> None:
    database = get_database(session_state).copy()
    dummy_database = load_dummy_database()
    database[table_name] = dummy_database[table_name].copy()
    set_database(session_state, database)
    session_state[DATABASE_MESSAGE_KEY] = f"{table_name}_data_loaded"


def import_growth_view(session_state: Any, uploaded_df: pd.DataFrame) -> None:
    database = get_database(session_state)
    growth_df = uploaded_df.copy()
    for column in GROWTH_VIEW_COLUMNS:
        if column not in growth_df.columns:
            growth_df[column] = ""
    growth_df = _clean_rows(growth_df[GROWTH_VIEW_COLUMNS])
    strategy_id = ensure_default_strategy(database)
    period_map = _upsert_periods(database, growth_df["時期"].tolist())

    rows = []
    for _, row in growth_df.iterrows():
        period_code = _stringify(row["時期"])
        if not period_code:
            continue
        rows.append(
            {
                "sales_target_id": len(rows) + 1,
                "strategy_id": strategy_id,
                "period_id": period_map[period_code],
                "target_amount": _to_int(row["お金"], 0),
            }
        )
    database["sales_target"] = validate_table("sales_target", pd.DataFrame(rows, columns=TABLE_DEFINITIONS["sales_target"].columns))
    set_database(session_state, database)


def import_career_view(session_state: Any, uploaded_df: pd.DataFrame) -> None:
    database = get_database(session_state)
    career_df = uploaded_df.copy()
    for column in CAREER_VIEW_COLUMNS:
        if column not in career_df.columns:
            career_df[column] = ""
    career_df = _clean_rows(career_df[CAREER_VIEW_COLUMNS])
    employee_map = _upsert_employees(database, career_df["ID"].tolist())
    period_map = _upsert_periods(database, career_df["時期"].tolist())
    skill_map = _upsert_skills(database, career_df["スキル"].tolist())

    rows = []
    for _, row in career_df.iterrows():
        employee_code = _stringify(row["ID"])
        period_code = _stringify(row["時期"])
        skill_name = _stringify(row["スキル"])
        if not employee_code or not period_code or not skill_name:
            continue
        rows.append(
            {
                "career_goal_id": len(rows) + 1,
                "employee_id": employee_map[employee_code],
                "period_id": period_map[period_code],
                "desired_skill_id": skill_map[skill_name],
                "target_skill_level": max(1, min(_to_int(row["スキルのLv"], 1), 5)),
            }
        )
    database["career_goal"] = validate_table("career_goal", pd.DataFrame(rows, columns=TABLE_DEFINITIONS["career_goal"].columns))
    set_database(session_state, database)


def import_skill_view(session_state: Any, uploaded_df: pd.DataFrame) -> None:
    database = get_database(session_state)
    skill_df = uploaded_df.copy()
    for column in SKILL_VIEW_COLUMNS:
        if column not in skill_df.columns:
            skill_df[column] = ""
    skill_df = _clean_rows(skill_df[SKILL_VIEW_COLUMNS])
    employee_map = _upsert_employees(database, skill_df["ID"].tolist())
    skill_map = _upsert_skills(database, skill_df["スキル"].tolist())

    rows = []
    for _, row in skill_df.iterrows():
        employee_code = _stringify(row["ID"])
        skill_name = _stringify(row["スキル"])
        if not employee_code or not skill_name:
            continue
        rows.append(
            {
                "employee_skill_id": len(rows) + 1,
                "employee_id": employee_map[employee_code],
                "skill_id": skill_map[skill_name],
                "skill_level": max(1, min(_to_int(row["スキルのLv"], 1), 5)),
            }
        )
    database["employee_skill"] = validate_table("employee_skill", pd.DataFrame(rows, columns=TABLE_DEFINITIONS["employee_skill"].columns))
    set_database(session_state, database)


def _ranked_skill_ids(database: dict[str, pd.DataFrame]) -> list[int]:
    ranked = []
    career = database["career_goal"]
    if not career.empty:
        ranked = career["desired_skill_id"].value_counts().index.tolist()
    if not ranked and not database["employee_skill"].empty:
        ranked = database["employee_skill"]["skill_id"].value_counts().index.tolist()
    if not ranked and not database["skill"].empty:
        ranked = database["skill"]["skill_id"].tolist()
    return [int(skill_id) for skill_id in ranked]


def generate_projects(session_state: Any) -> None:
    database = get_database(session_state)
    sales_target = database["sales_target"]
    periods = database["fiscal_period"]
    skills = database["skill"]
    skill_ids = _ranked_skill_ids(database)
    if sales_target.empty or periods.empty or not skill_ids:
        database["project"] = empty_table("project")
        database["project_required_skill"] = empty_table("project_required_skill")
        set_database(session_state, database)
        return

    period_map = periods.set_index("period_id")["period_code"].to_dict()
    skill_name_map = skills.set_index("skill_id")["skill_name"].to_dict()
    project_rows = []
    requirement_rows = []
    project_id = 1
    requirement_id = 1
    skill_index = 0

    for _, target_row in sales_target.sort_values(["period_id", "sales_target_id"]).iterrows():
        target_amount = int(target_row["target_amount"])
        project_count = 2 if target_amount >= 1800 else 1
        headcount = 2 if target_amount >= 2000 else 1
        for offset in range(project_count):
            skill_id = skill_ids[skill_index % len(skill_ids)]
            skill_name = _stringify(skill_name_map.get(skill_id, f"Skill {skill_id}"))
            period_code = _stringify(period_map.get(int(target_row["period_id"]), "未設定"))
            project_rows.append(
                {
                    "project_id": project_id,
                    "sales_target_id": int(target_row["sales_target_id"]),
                    "period_id": int(target_row["period_id"]),
                    "project_code": f"PJ-{project_id:03d}",
                    "project_name": f"{period_code} {skill_name}案件 {offset + 1}",
                    "project_status": "draft",
                }
            )
            requirement_rows.append(
                {
                    "project_required_skill_id": requirement_id,
                    "project_id": project_id,
                    "skill_id": skill_id,
                    "required_skill_level": max(1, min(5, 2 + (target_amount // 700) + offset)),
                    "required_headcount": headcount,
                }
            )
            project_id += 1
            requirement_id += 1
            skill_index += 1

    database["project"] = validate_table("project", pd.DataFrame(project_rows, columns=TABLE_DEFINITIONS["project"].columns))
    database["project_required_skill"] = validate_table(
        "project_required_skill",
        pd.DataFrame(requirement_rows, columns=TABLE_DEFINITIONS["project_required_skill"].columns),
    )
    set_database(session_state, database)


def _candidate_scores(database: dict[str, pd.DataFrame]) -> pd.DataFrame:
    employee_skill = database["employee_skill"]
    if employee_skill.empty:
        return pd.DataFrame(columns=["employee_id", "skill_id", "skill_level", "target_bonus"])
    scores = employee_skill.copy()
    scores["target_bonus"] = 0
    if not database["career_goal"].empty:
        career = (
            database["career_goal"]
            .groupby(["employee_id", "desired_skill_id"], as_index=False)["target_skill_level"]
            .max()
            .rename(columns={"desired_skill_id": "skill_id"})
        )
        scores = scores.merge(career, on=["employee_id", "skill_id"], how="left")
        scores["target_bonus"] = scores["target_skill_level"].fillna(0).astype(int)
        scores = scores.drop(columns=["target_skill_level"])
    return scores


def generate_assignments(session_state: Any) -> None:
    database = get_database(session_state)
    projects = database["project"]
    requirements = database["project_required_skill"]
    if projects.empty or requirements.empty or database["employee_skill"].empty:
        database["assignment"] = empty_table("assignment")
        set_database(session_state, database)
        return

    candidate_scores = _candidate_scores(database)
    project_period_map = projects.set_index("project_id")["period_id"].to_dict()
    assignment_rows = []
    assignment_id = 1

    for _, requirement in requirements.sort_values(["project_id", "project_required_skill_id"]).iterrows():
        project_id = int(requirement["project_id"])
        skill_id = int(requirement["skill_id"])
        required_level = int(requirement["required_skill_level"])
        headcount = int(requirement["required_headcount"])
        candidates = candidate_scores[candidate_scores["skill_id"] == skill_id].copy()
        if candidates.empty:
            candidates = candidate_scores.copy()
        candidates["score"] = candidates["skill_level"] * 10 + candidates["target_bonus"] * 3
        candidates.loc[candidates["skill_level"] >= required_level, "score"] += 20
        candidates = candidates.sort_values(["score", "employee_id"], ascending=[False, True])
        selected = candidates.head(headcount)
        if selected.empty:
            continue
        allocation_ratio = round(1 / len(selected), 2)
        for _, candidate in selected.iterrows():
            assignment_rows.append(
                {
                    "assignment_id": assignment_id,
                    "project_id": project_id,
                    "employee_id": int(candidate["employee_id"]),
                    "assignment_period_id": int(project_period_map[project_id]),
                    "assigned_skill_id": skill_id,
                    "allocation_ratio": allocation_ratio,
                }
            )
            assignment_id += 1

    database["assignment"] = validate_table("assignment", pd.DataFrame(assignment_rows, columns=TABLE_DEFINITIONS["assignment"].columns))
    set_database(session_state, database)


def _join_periods(df: pd.DataFrame, periods: pd.DataFrame, left_on: str = "period_id") -> pd.DataFrame:
    return df.merge(periods.rename(columns={"period_id": left_on, "period_code": "時期"}), on=left_on, how="left")


def build_growth_view(database: dict[str, pd.DataFrame]) -> pd.DataFrame:
    sales_target = database["sales_target"]
    if sales_target.empty:
        return pd.DataFrame(columns=GROWTH_VIEW_COLUMNS)
    periods = database["fiscal_period"][["period_id", "period_code"]]
    view = _join_periods(sales_target, periods).rename(columns={"target_amount": "お金"})
    return view[["時期", "お金"]].sort_values("時期").reset_index(drop=True)


def build_career_view(database: dict[str, pd.DataFrame]) -> pd.DataFrame:
    career_goal = database["career_goal"]
    if career_goal.empty:
        return pd.DataFrame(columns=CAREER_VIEW_COLUMNS)
    employees = database["employee"][["employee_id", "employee_code"]]
    periods = database["fiscal_period"][["period_id", "period_code"]]
    skills = database["skill"][["skill_id", "skill_name"]]
    view = career_goal.merge(employees, on="employee_id", how="left")
    view = view.merge(periods.rename(columns={"period_id": "period_id", "period_code": "時期"}), on="period_id", how="left")
    view = view.merge(skills.rename(columns={"skill_id": "desired_skill_id", "skill_name": "スキル"}), on="desired_skill_id", how="left")
    view = view.rename(columns={"employee_code": "ID", "target_skill_level": "スキルのLv"})
    return view[CAREER_VIEW_COLUMNS].sort_values(["ID", "時期", "スキル"]).reset_index(drop=True)


def build_skill_view(database: dict[str, pd.DataFrame]) -> pd.DataFrame:
    employee_skill = database["employee_skill"]
    if employee_skill.empty:
        return pd.DataFrame(columns=SKILL_VIEW_COLUMNS)
    employees = database["employee"][["employee_id", "employee_code"]]
    skills = database["skill"][["skill_id", "skill_name"]]
    view = employee_skill.merge(employees, on="employee_id", how="left")
    view = view.merge(skills, on="skill_id", how="left")
    view = view.rename(columns={"employee_code": "ID", "skill_name": "スキル", "skill_level": "スキルのLv"})
    return view[SKILL_VIEW_COLUMNS].sort_values(["ID", "スキル"]).reset_index(drop=True)


def build_project_view(database: dict[str, pd.DataFrame]) -> pd.DataFrame:
    projects = database["project"]
    requirements = database["project_required_skill"]
    if projects.empty or requirements.empty:
        return pd.DataFrame(columns=PROJECT_VIEW_COLUMNS)
    sales_target = database["sales_target"][["sales_target_id", "target_amount"]]
    periods = database["fiscal_period"][["period_id", "period_code"]]
    skills = database["skill"][["skill_id", "skill_name"]]
    view = projects.merge(sales_target, on="sales_target_id", how="left")
    view = view.merge(periods, on="period_id", how="left")
    view = view.merge(requirements, on="project_id", how="left")
    view = view.merge(skills, on="skill_id", how="left")
    view = view.rename(
        columns={
            "project_code": "PJ ID",
            "period_code": "時期",
            "target_amount": "お金",
            "skill_name": "スキル",
            "required_skill_level": "スキルのLv",
        }
    )
    return view[PROJECT_VIEW_COLUMNS].sort_values(["PJ ID", "スキル"]).reset_index(drop=True)


def build_assignment_view(database: dict[str, pd.DataFrame]) -> pd.DataFrame:
    assignments = database["assignment"]
    if assignments.empty:
        return pd.DataFrame(columns=ASSIGNMENT_VIEW_COLUMNS)
    employees = database["employee"][["employee_id", "employee_code"]]
    projects = database["project"][["project_id", "project_code"]]
    periods = database["fiscal_period"][["period_id", "period_code"]]
    skills = database["skill"][["skill_id", "skill_name"]]
    requirements = database["project_required_skill"][["project_id", "skill_id", "required_skill_level"]]
    view = assignments.merge(employees, on="employee_id", how="left")
    view = view.merge(projects, on="project_id", how="left")
    view = view.merge(periods.rename(columns={"period_id": "assignment_period_id", "period_code": "時期"}), on="assignment_period_id", how="left")
    view = view.merge(requirements.rename(columns={"skill_id": "assigned_skill_id"}), on=["project_id", "assigned_skill_id"], how="left")
    view = view.merge(skills.rename(columns={"skill_id": "assigned_skill_id", "skill_name": "スキル"}), on="assigned_skill_id", how="left")
    view = view.rename(columns={"employee_code": "ID", "project_code": "PJ ID", "required_skill_level": "スキルのLv"})
    return view[ASSIGNMENT_VIEW_COLUMNS].sort_values(["PJ ID", "ID"]).reset_index(drop=True)


def view_dataframe(table_key: str, database: dict[str, pd.DataFrame]) -> pd.DataFrame:
    builders = {
        "growth": build_growth_view,
        "career": build_career_view,
        "skill": build_skill_view,
        "project": build_project_view,
        "assignment": build_assignment_view,
    }
    return builders[table_key](database)


def save_table(session_state: Any, table_name: str, edited_df: pd.DataFrame) -> None:
    database = get_database(session_state).copy()
    database[table_name] = validate_table(table_name, edited_df)
    set_database(session_state, database)


def table_payload(database: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    payload = []
    for table_name in TABLE_ORDER:
        definition = TABLE_DEFINITIONS[table_name]
        payload.append(
            {
                "name": table_name,
                "label": definition.label,
                "role": definition.role,
                "description": definition.description,
                "columns": definition.columns,
                "row_count": int(len(database[table_name])),
            }
        )
    return payload


def build_master_er_mermaid() -> str:
    return """erDiagram
    SALES_STRATEGY {
        int strategy_id PK
        string strategy_code UK
        string strategy_name
        string valid_from
        string valid_to
    }
    FISCAL_PERIOD {
        int period_id PK
        string period_code UK
        string period_start
        string period_end
    }
    SALES_TARGET {
        int sales_target_id PK
        int strategy_id FK
        int period_id FK
        int target_amount
    }
    SKILL {
        int skill_id PK
        string skill_code UK
        string skill_name UK
        string skill_category
    }
    EMPLOYEE {
        int employee_id PK
        string employee_code UK
        string employee_name
        string department
    }
    EMPLOYEE_SKILL {
        int employee_skill_id PK
        int employee_id FK
        int skill_id FK
        int skill_level
    }
    CAREER_GOAL {
        int career_goal_id PK
        int employee_id FK
        int period_id FK
        int desired_skill_id FK
        int target_skill_level
    }
    PROJECT {
        int project_id PK
        int sales_target_id FK
        int period_id FK
        string project_code UK
        string project_name
        string project_status
    }
    PROJECT_REQUIRED_SKILL {
        int project_required_skill_id PK
        int project_id FK
        int skill_id FK
        int required_skill_level
        int required_headcount
    }
    ASSIGNMENT {
        int assignment_id PK
        int project_id FK
        int employee_id FK
        int assignment_period_id FK
        int assigned_skill_id FK
        float allocation_ratio
    }

    SALES_STRATEGY ||--o{ SALES_TARGET : "defines"
    FISCAL_PERIOD ||--o{ SALES_TARGET : "targets"
    SALES_TARGET ||--o{ PROJECT : "drives"
    FISCAL_PERIOD ||--o{ PROJECT : "planned"
    PROJECT ||--o{ PROJECT_REQUIRED_SKILL : "requires"
    SKILL ||--o{ PROJECT_REQUIRED_SKILL : "classifies"
    EMPLOYEE ||--o{ EMPLOYEE_SKILL : "has"
    SKILL ||--o{ EMPLOYEE_SKILL : "owns"
    EMPLOYEE ||--o{ CAREER_GOAL : "plans"
    FISCAL_PERIOD ||--o{ CAREER_GOAL : "targets"
    SKILL ||--o{ CAREER_GOAL : "aims"
    PROJECT ||--o{ ASSIGNMENT : "allocates"
    EMPLOYEE ||--o{ ASSIGNMENT : "works"
    SKILL ||--o{ ASSIGNMENT : "uses"
    FISCAL_PERIOD ||--o{ ASSIGNMENT : "during"
"""


def build_master_wiki_markdown() -> str:
    lines = [
        "# マスタ管理Wiki",
        "",
        "## 役割",
        "このセクションでは、サービスが保持する正規化済みテーブルを直接閲覧・編集します。",
        "各ページの編集結果は同一セッション内で保持され、入力ページや出力ページはこれらのテーブルを JOIN して表示します。",
        "",
        "## ER図",
        "```mermaid",
        build_master_er_mermaid().rstrip(),
        "```",
        "",
        "## テーブル一覧",
        "",
    ]
    for table_name in TABLE_ORDER:
        definition = TABLE_DEFINITIONS[table_name]
        lines.append(f"### {definition.label}")
        lines.append(f"- 種別: {definition.role}")
        lines.append(f"- 役割: {definition.description}")
        lines.append(f"- カラム: {', '.join(definition.columns)}")
        lines.append("")
    return "\n".join(lines)


def export_artifacts(session_state: Any) -> list[Path]:
    database = get_database(session_state)
    data_dir = EXPORT_DIR / "data"
    schema_dir = EXPORT_DIR / "schema"
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    schema_dir.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    for table_name in TABLE_ORDER:
        csv_path = data_dir / f"{table_name}.csv"
        json_path = data_dir / f"{table_name}.json"
        database[table_name].to_csv(csv_path, index=False, encoding="utf-8-sig")
        database[table_name].to_json(json_path, orient="records", force_ascii=False, indent=2)
        written_paths.extend([csv_path, json_path])

    schema_path = schema_dir / "database_schema.json"
    schema_path.write_text(json.dumps(table_payload(database), ensure_ascii=False, indent=2), encoding="utf-8")
    written_paths.append(schema_path)

    wiki_md = DOCS_DIR / "master_data_wiki.md"
    er_mmd = DOCS_DIR / "master_data_er.mmd"
    wiki_md.write_text(build_master_wiki_markdown(), encoding="utf-8")
    er_mmd.write_text(build_master_er_mermaid(), encoding="utf-8")
    written_paths.extend([wiki_md, er_mmd])
    return written_paths
