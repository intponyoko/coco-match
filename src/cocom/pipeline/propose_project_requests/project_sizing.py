from typing import Any

import pandas as pd

from cocom.pipeline.common.table import records
from cocom.pipeline.common.periods import fiscal_period_code_by_offset
from cocom.schema import ProjectSizingRecommendation


DEFAULT_BILLABLE_CAPACITY_RATIO = 0.75
DEFAULT_MIN_LOAD_RATIO = 0.65
DEFAULT_MAX_LOAD_RATIO = 0.95


def project_training_policy(recommendation: dict[str, Any]) -> tuple[bool, int]:
    theme_text = (
        f"{recommendation['theme']};{recommendation['customer_pain']};"
        f"{recommendation['delivery_model']}"
    ).lower()
    observed_revenue = float(recommendation["observed_revenue_mean"])
    observed_duration = float(recommendation["observed_duration_mean"])
    planned_revenue = float(recommendation["planned_revenue"])
    scale_gap_bonus = 0
    if planned_revenue >= 20_000_000 or observed_revenue >= 80_000_000:
        scale_gap_bonus = 2
    elif planned_revenue >= 10_000_000 or observed_revenue >= 40_000_000:
        scale_gap_bonus = 1
    if any(
        keyword in theme_text
        for keyword in [
            "regulated",
            "regulatory",
            "security",
            "risk",
            "public_sector",
            "executive",
        ]
    ):
        return True, min(3, 1 + scale_gap_bonus)
    if observed_revenue >= 100_000_000 or observed_duration >= 10:
        return True, min(5, 2 + scale_gap_bonus)
    if any(
        keyword in theme_text
        for keyword in [
            "adoption",
            "customer_success",
            "service_operations",
            "runbook",
            "rollout",
            "loyalty",
            "citizen_service",
            "enablement",
        ]
    ):
        return True, min(10, 6 + scale_gap_bonus)
    if any(keyword in theme_text for keyword in ["operate", "operations", "crm"]):
        return True, min(8, 4 + scale_gap_bonus)
    return True, min(7, 3 + scale_gap_bonus)


def project_duration_months(account_theme: dict[str, Any]) -> int:
    observed_revenue = max(1.0, float(account_theme["observed_revenue_mean"]))
    observed_duration = max(1.0, float(account_theme["observed_duration_mean"]))
    revenue_scale = max(0.5, float(account_theme["planned_revenue"]) / observed_revenue)
    return max(3, min(12, round(observed_duration * revenue_scale**0.5)))


def monthly_plan_targets(
    sales_plans: pd.DataFrame,
    industry_code: str,
) -> dict[str, float]:
    rows = sales_plans[sales_plans["industry_code"] == industry_code]
    return {
        str(row["period_code"]): float(row["target_revenue"])
        for row in records(rows)
    }


def expanded_project_revenue(
    fiscal_periods: pd.DataFrame,
    start_period_code: str,
    duration_months: int,
    estimated_revenue: int,
) -> dict[str, float]:
    monthly_revenue = estimated_revenue / max(duration_months, 1)
    return {
        fiscal_period_code_by_offset(fiscal_periods, start_period_code, offset): monthly_revenue
        for offset in range(duration_months)
    }


def annual_plan_period_codes(sales_plans: pd.DataFrame) -> list[str]:
    return sorted(str(period_code) for period_code in sales_plans["period_code"].unique())


def monthly_standard_fte_target(staffs: pd.DataFrame | None) -> tuple[float, float, float]:
    staff_count = len(staffs) if staffs is not None and not staffs.empty else 20
    baseline = staff_count * DEFAULT_BILLABLE_CAPACITY_RATIO
    return (
        baseline * DEFAULT_MIN_LOAD_RATIO,
        baseline,
        baseline * DEFAULT_MAX_LOAD_RATIO,
    )


def evidence_ids_for_recommendation(recommendation: dict[str, Any]) -> list[str]:
    return [
        case_id.strip()
        for case_id in str(recommendation["evidence_case_ids"]).split(";")
        if case_id.strip()
    ]


def estimated_standard_fte_profile(
    fiscal_periods: pd.DataFrame,
    past_case_roles: pd.DataFrame,
    evidence_ids: list[str],
    start_period_code: str,
    duration_months: int,
) -> dict[str, float]:
    role_rows = past_case_roles[past_case_roles["case_id"].isin(evidence_ids)]
    profile: dict[str, float] = {}
    if role_rows.empty:
        return profile

    for role_row in records(role_rows):
        phase_start = max(1, round(float(role_row["phase_start_month"])))
        phase_end = max(phase_start, round(float(role_row["phase_end_month"])))
        first_period_code = str(fiscal_periods.sort_values("start").iloc[0]["code"])
        if start_period_code == first_period_code:
            opening_shift = min(2, max(0, phase_start - 1))
            phase_start -= opening_shift
            phase_end = max(phase_start, phase_end - opening_shift)
        phase_end = min(duration_months, phase_end)
        fte = (
            float(role_row["headcount"])
            * float(role_row["allocation_percentage"])
            / 100
        )
        for offset in range(phase_start - 1, phase_end):
            period_code = fiscal_period_code_by_offset(
                fiscal_periods,
                start_period_code,
                offset,
            )
            profile[period_code] = profile.get(period_code, 0.0) + fte
    return profile


def choose_start_period(
    sales_plans: pd.DataFrame,
    fiscal_periods: pd.DataFrame,
    allocated_by_industry_period: dict[tuple[str, str], float],
    allocated_fte_by_period: dict[str, float],
    allocated_start_counts: dict[str, int],
    past_case_roles: pd.DataFrame,
    staffs: pd.DataFrame | None,
    recommendation: dict[str, Any],
    duration_months: int,
) -> str:
    industry_code = str(recommendation["industry_code"])
    targets = monthly_plan_targets(sales_plans, industry_code)
    candidate_periods = list(targets)
    if not candidate_periods:
        return str(fiscal_periods.iloc[0]["code"])

    annual_period_codes = annual_plan_period_codes(sales_plans)
    min_fte, target_fte, max_fte = monthly_standard_fte_target(staffs)
    evidence_ids = evidence_ids_for_recommendation(recommendation)

    def revenue_score(start_period_code: str) -> float:
        addition = expanded_project_revenue(
            fiscal_periods,
            start_period_code,
            duration_months,
            int(recommendation["planned_revenue"]),
        )
        score = 0.0
        for period_code, target_revenue in targets.items():
            current = allocated_by_industry_period.get((industry_code, period_code), 0.0)
            next_value = current + addition.get(period_code, 0.0)
            score += ((target_revenue - next_value) / max(target_revenue, 1.0)) ** 2
        return score

    def fte_score(start_period_code: str) -> float:
        addition = estimated_standard_fte_profile(
            fiscal_periods,
            past_case_roles,
            evidence_ids,
            start_period_code,
            duration_months,
        )
        score = 0.0
        annual_period_set = set(annual_period_codes)
        for period_code in annual_period_codes:
            next_value = allocated_fte_by_period.get(period_code, 0.0) + addition.get(
                period_code,
                0.0,
            )
            if next_value < min_fte:
                score += ((min_fte - next_value) / max(target_fte, 1.0)) ** 2
            if next_value > max_fte:
                score += 4 * ((next_value - max_fte) / max(target_fte, 1.0)) ** 2
            score += 0.2 * ((target_fte - next_value) / max(target_fte, 1.0)) ** 2
        spillover_fte = sum(
            fte for period_code, fte in addition.items() if period_code not in annual_period_set
        )
        score += 2 * (spillover_fte / max(target_fte, 1.0)) ** 2
        return score

    def candidate_score(start_period_code: str) -> tuple[float, float, str]:
        first_period_code = annual_period_codes[0]
        start_limit = 4 if start_period_code == first_period_code else 2
        concentration_penalty = max(
            0,
            allocated_start_counts.get(start_period_code, 0) + 1 - start_limit,
        )
        return (
            fte_score(start_period_code) + 20 * concentration_penalty**2,
            revenue_score(start_period_code),
            start_period_code,
        )

    return min(candidate_periods, key=candidate_score)


def add_project_allocation(
    fiscal_periods: pd.DataFrame,
    allocated_by_industry_period: dict[tuple[str, str], float],
    industry_code: str,
    start_period_code: str,
    duration_months: int,
    estimated_revenue: int,
) -> None:
    for period_code, revenue in expanded_project_revenue(
        fiscal_periods,
        start_period_code,
        duration_months,
        estimated_revenue,
    ).items():
        key = (industry_code, period_code)
        allocated_by_industry_period[key] = allocated_by_industry_period.get(key, 0.0) + revenue


def add_fte_allocation(
    fiscal_periods: pd.DataFrame,
    allocated_fte_by_period: dict[str, float],
    past_case_roles: pd.DataFrame,
    evidence_ids: list[str],
    start_period_code: str,
    duration_months: int,
) -> None:
    for period_code, fte in estimated_standard_fte_profile(
        fiscal_periods,
        past_case_roles,
        evidence_ids,
        start_period_code,
        duration_months,
    ).items():
        allocated_fte_by_period[period_code] = (
            allocated_fte_by_period.get(period_code, 0.0) + fte
        )


def size_project_specs(
    account_recommendations: pd.DataFrame,
    sales_plans: pd.DataFrame,
    fiscal_periods: pd.DataFrame,
    past_case_roles: pd.DataFrame,
    staffs: pd.DataFrame | None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    allocated_by_industry_period: dict[tuple[str, str], float] = {}
    allocated_fte_by_period: dict[str, float] = {}
    allocated_start_counts: dict[str, int] = {}
    for index, recommendation in enumerate(
        sorted(
            records(account_recommendations),
            key=lambda row: (str(row["industry_code"]), -int(row["planned_revenue"])),
        ),
        start=1,
    ):
        training_allowed, training_max_skill_gap = project_training_policy(
            recommendation
        )
        duration_months = project_duration_months(recommendation)
        start_period_code = choose_start_period(
            sales_plans,
            fiscal_periods,
            allocated_by_industry_period,
            allocated_fte_by_period,
            allocated_start_counts,
            past_case_roles,
            staffs,
            recommendation,
            duration_months,
        )
        estimated_revenue = int(recommendation["planned_revenue"])
        evidence_ids = evidence_ids_for_recommendation(recommendation)
        add_project_allocation(
            fiscal_periods,
            allocated_by_industry_period,
            str(recommendation["industry_code"]),
            start_period_code,
            duration_months,
            estimated_revenue,
        )
        add_fte_allocation(
            fiscal_periods,
            allocated_fte_by_period,
            past_case_roles,
            evidence_ids,
            start_period_code,
            duration_months,
        )
        allocated_start_counts[start_period_code] = (
            allocated_start_counts.get(start_period_code, 0) + 1
        )
        rows.append(
            {
                "sales_plan_code": recommendation["sales_plan_code"],
                "project_spec_code": f"PSP-{index:06d}",
                "industry_code": recommendation["industry_code"],
                "account_code": recommendation["account_code"],
                "account_name": recommendation["account_name"],
                "account_segment": recommendation["account_segment"],
                "solution_code": recommendation["solution_code"],
                "start_period_code": start_period_code,
                "estimated_revenue": estimated_revenue,
                "duration_months": duration_months,
                "theme": recommendation["theme"],
                "customer_pain": recommendation["customer_pain"],
                "evidence_case_ids": recommendation["evidence_case_ids"],
                "grounding_score": round(
                    (
                        float(recommendation["theme_score"])
                        + float(recommendation["account_score"])
                    )
                    / 2,
                    6,
                ),
                "project_training_allowed": training_allowed,
                "project_training_max_skill_gap": training_max_skill_gap,
                "sizing_method": "theme_account_planned_revenue",
                "delivery_model": recommendation["delivery_model"],
            }
        )
    return ProjectSizingRecommendation.data_frame(rows)
