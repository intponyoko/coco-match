from typing import Any, cast

import pandas as pd

from .config import (
    config_list,
    config_str_lists,
    config_table,
    positive_int,
)
from .staff import department_code_prefix


def skill_max_level(config: dict[str, Any]) -> int:
    return int(config_table(config, "defaults")["skill_max_level"])


def generate_fiscal_periods(months: int) -> list[dict]:
    positive_int("fiscal_months", months)
    start = pd.Timestamp("2026-01-01")
    rows = []
    for index in range(months):
        period_start = start + pd.DateOffset(months=index)
        period_end = start + pd.DateOffset(months=index + 1) - pd.Timedelta(days=1)
        code = period_start.date().isoformat()
        rows.append(
            {
                "code": code,
                "start": period_start.date().isoformat(),
                "end": period_end.date().isoformat(),
            }
        )
    return rows


def generate_departments(config: dict[str, Any]) -> list[dict]:
    return [
        {"code": f"DEP-{index + 1:03d}", "name": name}
        for index, name in enumerate(config_list(config, "departments"))
    ]


def generate_titles(config: dict[str, Any]) -> list[dict]:
    title_prices = cast(dict[str, int], config_table(config, "title_prices"))
    return [
        {
            "code": f"TITLE-{index + 1:03d}",
            "name": name,
            "price": int(title_prices[name]),
        }
        for index, name in enumerate(config_list(config, "staff_titles"))
    ]


def retained_skill_codes(config: dict[str, Any], role_skills: list[dict]) -> set[str]:
    management = config_table(config, "management")
    return {
        *{str(role_skill["skill_code"]) for role_skill in role_skills},
        *cast(list[str], management["title_management_skills"]),
    }


def generate_skills(config: dict[str, Any], role_skills: list[dict]) -> list[dict]:
    rows = []
    max_level = skill_max_level(config)
    retained_codes = retained_skill_codes(config, role_skills)
    for department_name, skill_names in config_str_lists(config, "skills").items():
        department_code = department_code_prefix(department_name)
        for index, skill_name in enumerate(skill_names, start=1):
            skill_code = f"SKL-{department_code}-{index:02d}"
            if skill_code not in retained_codes:
                continue
            rows.append(
                {
                    "code": skill_code,
                    "name": skill_name,
                    "max_level": max_level,
                }
            )
    return rows


def generate_roles(config: dict[str, Any]) -> list[dict]:
    rows = []
    for department_name, role_names in config_str_lists(config, "roles").items():
        department_code = department_code_prefix(department_name)
        for index, role_name in enumerate(role_names, start=1):
            role_code = f"ROLE-{department_code}-{index:02d}"
            rows.append(
                {
                    "code": role_code,
                    "name": role_name,
                }
            )
    return rows


def generate_role_skills(config: dict[str, Any], roles: list[dict]) -> list[dict]:
    rows = []
    role_skill_generation = config_table(config, "role_skill_generation")
    required_limit = int(role_skill_generation["required_limit_per_role"])
    valid_role_codes = {str(role["code"]) for role in roles}
    role_skills = cast(
        dict[str, list[dict[str, Any]]],
        config_table(config, "role_skills"),
    )
    role_skills = {
        role_code: skills
        for role_code, skills in role_skills.items()
        if role_code in valid_role_codes
    }
    for role_code, skills in role_skills.items():
        required_seen = 0
        for skill in skills:
            configured_required = bool(skill["required"])
            is_required = configured_required and required_seen < required_limit
            if configured_required:
                required_seen += 1
            rows.append(
                {
                    "role_code": role_code,
                    "skill_code": str(skill["skill"]),
                    "skill_level": int(skill["level"]),
                    "required": is_required,
                }
            )

    required_counts: dict[str, int] = {}
    for row in rows:
        role_code = str(row["role_code"])
        if not bool(row["required"]):
            continue
        required_counts[role_code] = required_counts.get(role_code, 0) + 1
        if required_counts[role_code] > required_limit:
            row["required"] = False
    return rows


def generate_industries(config: dict[str, Any]) -> list[dict]:
    return [
        {"code": f"IND-{index + 1:03d}", "name": name}
        for index, name in enumerate(config_list(config, "industries"))
    ]


def generate_solutions(config: dict[str, Any]) -> list[dict]:
    return [
        {"code": f"SOL-{index + 1:03d}", "name": name}
        for index, name in enumerate(config_list(config, "solutions"))
    ]


def generate_accounts(config: dict[str, Any], industries: list[dict]) -> list[dict]:
    industry_by_name = {
        str(industry["name"]): str(industry["code"]) for industry in industries
    }
    rows = []
    account_config = cast(
        dict[str, list[dict[str, Any]]],
        config_table(config, "accounts"),
    )
    for industry_index, industry in enumerate(industries, start=1):
        industry_name = str(industry["name"])
        for account_index, account in enumerate(account_config[industry_name], start=1):
            rows.append(
                {
                    "code": f"ACC-{industry_index:03d}-{account_index:02d}",
                    "name": str(account["name"]),
                    "industry_code": industry_by_name[industry_name],
                    "segment": str(account["segment"]),
                    "revenue_potential": int(account["revenue_potential"]),
                }
            )
    return rows
