import pandas as pd

from cocom.pipeline.common.periods import (
    fiscal_period_code_by_offset,
    fiscal_period_end_code,
    normalize_weights,
)


def role_mix_for_evidence(
    past_case_roles: pd.DataFrame,
    evidence_ids: list[str],
) -> dict[str, float]:
    rows = past_case_roles[past_case_roles["case_id"].isin(evidence_ids)].copy()
    if rows.empty:
        return {}
    rows["phase_months"] = (
        rows["phase_end_month"] - rows["phase_start_month"] + 1
    ).clip(lower=1)
    role_weights = (
        rows.groupby("role_code")
        .apply(
            lambda group: float(
                (
                    group["headcount"]
                    * group["allocation_percentage"]
                    * group["phase_months"]
                ).sum()
            ),
            include_groups=False,
        )
        .sort_values(ascending=False)
    )
    return normalize_weights(role_weights.to_dict())


def role_headcount_for_evidence(
    past_case_roles: pd.DataFrame,
    evidence_ids: list[str],
    role_mix: dict[str, float],
) -> dict[str, float]:
    rows = past_case_roles[past_case_roles["case_id"].isin(evidence_ids)]
    headcounts = rows.groupby("role_code")["headcount"].mean().to_dict()
    return {
        role_code: max(1, round(float(headcounts.get(role_code, 1))))
        for role_code in role_mix
    }


def role_allocation_for_evidence(
    past_case_roles: pd.DataFrame,
    evidence_ids: list[str],
    role_mix: dict[str, float],
) -> dict[str, int]:
    rows = past_case_roles[past_case_roles["case_id"].isin(evidence_ids)]
    allocations = rows.groupby("role_code")["allocation_percentage"].mean().to_dict()
    return {
        role_code: max(1, min(100, round(float(allocations.get(role_code, 50)))))
        for role_code in role_mix
    }


def role_phase_training_for_evidence(
    past_case_roles: pd.DataFrame,
    evidence_ids: list[str],
    role_mix: dict[str, float],
) -> dict[str, tuple[int, int]]:
    if "training_headcount" not in past_case_roles.columns:
        return {role_code: (0, 0) for role_code in role_mix}
    rows = past_case_roles[past_case_roles["case_id"].isin(evidence_ids)]
    result: dict[str, tuple[int, int]] = {}
    for role_code in role_mix:
        role_rows = rows[rows["role_code"] == role_code]
        if role_rows.empty:
            result[role_code] = (0, 0)
            continue
        training_slots = int(role_rows["training_headcount"].fillna(0).max())
        max_gap = (
            int(role_rows["role_phase_training_max_skill_gap"].fillna(0).max())
            if "role_phase_training_max_skill_gap" in role_rows.columns
            else 0
        )
        result[role_code] = (training_slots, max_gap if training_slots > 0 else 0)
    return result


def role_evidence_rows(
    past_case_roles: pd.DataFrame,
    evidence_ids: list[str],
    role_code: str,
) -> pd.DataFrame:
    return past_case_roles[
        (past_case_roles["case_id"].isin(evidence_ids))
        & (past_case_roles["role_code"] == role_code)
    ]


def role_phase_for_evidence(
    rows: pd.DataFrame,
) -> str:
    if rows.empty:
        return "delivery"
    return str(rows["phase"].mode().iloc[0])


def request_period_for_evidence(
    fiscal_periods: pd.DataFrame,
    rows: pd.DataFrame,
    opportunity_start_code: str,
    duration_months: int,
) -> tuple[str, str]:
    if rows.empty:
        start_month, end_month = 1, duration_months
    else:
        start_month = round(float(rows["phase_start_month"].mean()))
        end_month = round(float(rows["phase_end_month"].mean()))
    first_period_code = str(fiscal_periods.sort_values("start").iloc[0]["code"])
    if opportunity_start_code == first_period_code:
        opening_shift = min(2, max(0, start_month - 1))
        start_month -= opening_shift
        end_month = max(start_month, end_month - opening_shift)
    start_offset = max(0, start_month - 1)
    end_offset = max(
        start_offset + 1,
        min(duration_months, end_month),
    )
    start_code = fiscal_period_code_by_offset(
        fiscal_periods,
        opportunity_start_code,
        start_offset,
    )
    end_code = fiscal_period_end_code(
        fiscal_periods,
        opportunity_start_code,
        end_offset,
    )
    return start_code, end_code


def scaled_training_slots(
    base_slots: int,
    headcount: int,
    role_revenue: int,
    required_person_month: float,
    project_training_max_skill_gap: int,
) -> int:
    if base_slots <= 0 or project_training_max_skill_gap <= 0:
        return 0
    slots = base_slots
    if required_person_month >= 8 or role_revenue >= 8_000_000:
        slots += 1
    if required_person_month >= 16 or role_revenue >= 16_000_000:
        slots += 1
    return max(0, min(slots, max(1, headcount)))
