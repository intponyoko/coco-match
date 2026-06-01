from pathlib import Path
from typing import Any

import pandas as pd

from .career import generate_staff_career
from .config import config_table, positive_int
from .io import (
    load_config,
    parse_args,
    validate_sample,
    write_sample,
)
from .masters import (
    generate_accounts,
    generate_departments,
    generate_fiscal_periods,
    generate_industries,
    generate_role_skills,
    generate_roles,
    generate_skills,
    generate_solutions,
    generate_titles,
)
from .paths import (
    DEFAULT_CONFIG_PATH,
    OUTPUT_DIR,
    ROW_COUNT_KEYS,
)
from .sales_plan_generator import generate_sales_plans
from .staff import generate_staffs
from cocom.schema import (
    Account,
    Department,
    FiscalPeriod,
    Industry,
    Role,
    RoleSkill,
    SalesPlan,
    Skill,
    Solution,
    Staff,
    StaffCareer,
    Title,
)


def row_counts(config: dict[str, Any], rows: int | None, staffs: int | None) -> dict[str, int]:
    defaults = config_table(config, "defaults")
    counts = {name: int(defaults[name]) for name in ROW_COUNT_KEYS}
    if rows is not None:
        counts = {name: rows for name in counts}
    if staffs is not None:
        counts["staffs"] = staffs

    invalid = {name: count for name, count in counts.items() if count < 1}
    if invalid:
        details = ", ".join(f"{name}={count}" for name, count in invalid.items())
        raise ValueError(f"Row counts must be positive: {details}")
    return counts


def fiscal_month_count(
    defaults: dict[str, Any],
    fiscal_months: int | None,
) -> int:
    return positive_int(
        "fiscal_months",
        int(fiscal_months if fiscal_months is not None else defaults["fiscal_months"]),
    )


def career_skills_per_staff_count(
    defaults: dict[str, Any],
    staff_career_skills_per_staff: int | None,
) -> int:
    return positive_int(
        "staff_career_skills_per_staff",
        int(
            staff_career_skills_per_staff
            if staff_career_skills_per_staff is not None
            else defaults["staff_career_skills_per_staff"]
        ),
    )


def generate_sample_rows(
    config: dict[str, Any],
    rows: int | None = None,
    staffs: int | None = None,
    fiscal_months: int | None = None,
    staff_career_skills_per_staff: int | None = None,
    role_demand_rows: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict]]:
    defaults = config_table(config, "defaults")
    counts = row_counts(config, rows=rows, staffs=staffs)
    fiscal_period_rows = generate_fiscal_periods(
        fiscal_month_count(defaults, fiscal_months)
    )
    department_rows = generate_departments(config)
    title_rows = generate_titles(config)
    staff_rows = generate_staffs(config, counts["staffs"], department_rows, title_rows)
    role_rows = generate_roles(config)
    role_skill_rows = generate_role_skills(config, role_rows)
    skill_rows = generate_skills(config, role_skill_rows)
    industry_rows = generate_industries(config)
    solution_rows = generate_solutions(config)
    account_rows = generate_accounts(config, industry_rows)
    staff_career_rows = generate_staff_career(
        config,
        career_skills_per_staff_count(defaults, staff_career_skills_per_staff),
        staff_rows,
        title_rows,
        skill_rows,
        department_rows,
        role_skill_rows,
        fiscal_period_rows,
        role_demand_rows,
    )
    sales_plan_rows = generate_sales_plans(config, industry_rows, fiscal_period_rows)

    return {
        "fiscal_periods": fiscal_period_rows,
        "departments": department_rows,
        "titles": title_rows,
        "staffs": staff_rows,
        "skills": skill_rows,
        "roles": role_rows,
        "role_skills": role_skill_rows,
        "industries": industry_rows,
        "accounts": account_rows,
        "solutions": solution_rows,
        "staff_career": staff_career_rows,
        "sales_plans": sales_plan_rows,
    }


def write_generated_rows(
    generated_rows: dict[str, list[dict]],
    output_dir: Path,
) -> dict[str, pd.DataFrame]:
    return {
        "fiscal_periods": write_sample(
            "fiscal_periods", FiscalPeriod, generated_rows["fiscal_periods"], output_dir
        ),
        "departments": write_sample(
            "departments", Department, generated_rows["departments"], output_dir
        ),
        "titles": write_sample("titles", Title, generated_rows["titles"], output_dir),
        "staffs": write_sample("staffs", Staff, generated_rows["staffs"], output_dir),
        "skills": write_sample("skills", Skill, generated_rows["skills"], output_dir),
        "roles": write_sample("roles", Role, generated_rows["roles"], output_dir),
        "role_skills": write_sample(
            "role_skills", RoleSkill, generated_rows["role_skills"], output_dir
        ),
        "industries": write_sample(
            "industries", Industry, generated_rows["industries"], output_dir
        ),
        "accounts": write_sample(
            "accounts", Account, generated_rows["accounts"], output_dir
        ),
        "solutions": write_sample(
            "solutions", Solution, generated_rows["solutions"], output_dir
        ),
        "staff_career": write_sample(
            "staff_career", StaffCareer, generated_rows["staff_career"], output_dir
        ),
        "sales_plans": write_sample(
            "sales_plans", SalesPlan, generated_rows["sales_plans"], output_dir
        ),
    }


def validate_generated_rows(
    generated_rows: dict[str, list[dict]],
) -> dict[str, pd.DataFrame]:
    return {
        "fiscal_periods": validate_sample(
            FiscalPeriod, generated_rows["fiscal_periods"]
        ),
        "departments": validate_sample(Department, generated_rows["departments"]),
        "titles": validate_sample(Title, generated_rows["titles"]),
        "staffs": validate_sample(Staff, generated_rows["staffs"]),
        "skills": validate_sample(Skill, generated_rows["skills"]),
        "roles": validate_sample(Role, generated_rows["roles"]),
        "role_skills": validate_sample(RoleSkill, generated_rows["role_skills"]),
        "industries": validate_sample(Industry, generated_rows["industries"]),
        "accounts": validate_sample(Account, generated_rows["accounts"]),
        "solutions": validate_sample(Solution, generated_rows["solutions"]),
        "staff_career": validate_sample(StaffCareer, generated_rows["staff_career"]),
        "sales_plans": validate_sample(SalesPlan, generated_rows["sales_plans"]),
    }


def generate_sample_data(
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path = OUTPUT_DIR,
    rows: int | None = None,
    staffs: int | None = None,
    fiscal_months: int | None = None,
    staff_career_skills_per_staff: int | None = None,
) -> dict[str, pd.DataFrame]:
    config = load_config(config_path)
    role_demand_path = config_path.parent / "knowledge" / "past_cases" / "past_case_roles.csv"
    role_demand_rows = (
        pd.read_csv(role_demand_path).to_dict("records")
        if role_demand_path.exists()
        else None
    )
    generated_rows = generate_sample_rows(
        config,
        rows=rows,
        staffs=staffs,
        fiscal_months=fiscal_months,
        staff_career_skills_per_staff=staff_career_skills_per_staff,
        role_demand_rows=role_demand_rows,
    )
    return write_generated_rows(generated_rows, output_dir)


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "OUTPUT_DIR",
    "generate_sample_data",
    "generate_sample_rows",
    "validate_generated_rows",
    "write_generated_rows",
    "load_config",
    "parse_args",
]
