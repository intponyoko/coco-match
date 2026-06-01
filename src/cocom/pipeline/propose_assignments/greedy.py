from typing import Any

import pandas as pd

from cocom.pipeline.common.table import records
from .io import (
    MatchAssignmentsInput,
    MatchAssignmentsOutput,
)
from cocom.schema import MatchingTrace, OpportunityAssignment, StaffUtilization


MAX_UTILIZATION = 100


def capacity_available(
    utilization: dict[tuple[str, str], int],
    staff_code: str,
    period_codes: list[str],
    allocation: int,
) -> bool:
    return all(
        utilization.get((staff_code, period_code), 0) + allocation <= MAX_UTILIZATION
        for period_code in period_codes
    )


def standard_unassigned_reason(
    staff_rows: list[dict[str, Any]],
    selected_staff: set[str],
    role_requirements: list[dict[str, Any]],
    levels_by_staff: dict[str, dict[str, int]],
    utilization: dict[tuple[str, str], int],
    request_period_codes: list[str],
    allocation: int,
) -> str:
    skill_candidates = []
    for staff in staff_rows:
        staff_code = str(staff["code"])
        if staff_code in selected_staff:
            continue
        levels = levels_by_staff.get(staff_code, {})
        if staff_can_fill(role_requirements, levels):
            skill_candidates.append(staff_code)
    if not skill_candidates:
        return "no_skill_candidate"
    if not any(
        capacity_available(
            utilization,
            staff_code,
            request_period_codes,
            allocation,
        )
        for staff_code in skill_candidates
    ):
        return "skill_candidate_capacity_full"
    return "no_candidate_after_filter"


def training_unassigned_reason(
    staff_rows: list[dict[str, Any]],
    selected_staff: set[str],
    required: list[dict[str, Any]],
    levels_by_staff: dict[str, dict[str, int]],
    utilization: dict[tuple[str, str], int],
    request_period_codes: list[str],
    allocation: int,
    training_max_skill_gap: int,
) -> str:
    gap_candidates = []
    for staff in staff_rows:
        staff_code = str(staff["code"])
        if staff_code in selected_staff:
            continue
        levels = levels_by_staff.get(staff_code, {})
        if skill_gap(required, levels) <= training_max_skill_gap:
            gap_candidates.append(staff_code)
    if not gap_candidates:
        return "no_training_candidate_satisfies_gap"
    if not any(
        capacity_available(
            utilization,
            staff_code,
            request_period_codes,
            allocation,
        )
        for staff_code in gap_candidates
    ):
        return "training_candidate_capacity_full"
    return "no_training_candidate_after_filter"


def staff_skill_levels(staff_career: pd.DataFrame) -> dict[str, dict[str, int]]:
    levels: dict[str, dict[str, int]] = {}
    for row in records(staff_career):
        staff_code = str(row["staff_code"])
        skill_code = str(row["skill_code"])
        level = int(row["skill_level_current"])
        levels.setdefault(staff_code, {})
        levels[staff_code][skill_code] = max(
            levels[staff_code].get(skill_code, 0), level
        )
    return levels


def role_skill_requirements(
    role_skills: pd.DataFrame,
) -> dict[str, list[dict[str, Any]]]:
    requirements: dict[str, list[dict[str, Any]]] = {}
    for row in records(role_skills):
        requirements.setdefault(str(row["role_code"]), []).append(
            {
                "skill_code": str(row["skill_code"]),
                "skill_level": int(row["skill_level"]),
                "required": bool(row["required"]),
            }
        )
    return requirements


def title_rank_map(titles: pd.DataFrame) -> dict[str, int]:
    title_codes = [str(row["code"]) for row in records(titles)]
    return {title_code: index for index, title_code in enumerate(title_codes)}


def preference_rank_map(
    staff_preference_options: pd.DataFrame | None,
) -> dict[tuple[str, str], int]:
    if staff_preference_options is None or staff_preference_options.empty:
        return {}
    rank_by_status = {
        "selected": -40,
        "high": -30,
        "medium": -15,
        "low": -5,
        "not_selected": 0,
        "": 0,
        "not_interested": 80,
        "avoid": 80,
        "unavailable": 200,
    }
    ranks: dict[tuple[str, str], int] = {}
    for row in records(staff_preference_options):
        staff_code = str(row.get("staff_code", ""))
        request_code = str(row.get("opportunity_request_code", ""))
        if not staff_code or not request_code:
            continue
        status = str(row.get("preference_status", "not_selected"))
        rank = rank_by_status.get(status, 0)
        key = (staff_code, request_code)
        ranks[key] = min(ranks.get(key, rank), rank)
    return ranks


def request_priority(
    request: dict[str, Any],
    requirements: dict[str, list[dict[str, Any]]],
) -> tuple[int, int, int, str]:
    role_requirements = requirements.get(str(request["role_code"]), [])
    required = [req for req in role_requirements if req["required"]]
    required_level_sum = sum(req["skill_level"] for req in required)
    return (
        -len(required),
        -required_level_sum,
        -int(request["headcount"]),
        str(request["code"]),
    )


def candidate_score(
    staff: dict[str, Any],
    required: list[dict[str, Any]],
    optional: list[dict[str, Any]],
    levels: dict[str, int],
    title_ranks: dict[str, int],
    utilization: int,
    preference_rank: int,
) -> tuple[int, int, int, int, int, str]:
    required_surplus = sum(
        levels.get(req["skill_code"], 0) - req["skill_level"] for req in required
    )
    optional_matches = sum(
        1 for req in optional if levels.get(req["skill_code"], 0) >= req["skill_level"]
    )
    total_level = sum(levels.values())
    title_rank = title_ranks[str(staff["title_code"])]
    return (
        preference_rank,
        required_surplus,
        -optional_matches,
        total_level,
        utilization + title_rank,
        str(staff["code"]),
    )


def training_candidate_score(
    staff: dict[str, Any],
    required: list[dict[str, Any]],
    optional: list[dict[str, Any]],
    levels: dict[str, int],
    title_ranks: dict[str, int],
    utilization: int,
    assignment_count: int,
    preference_rank: int,
) -> tuple[int, int, int, int, int, int, int, str]:
    gap = skill_gap(required, levels)
    optional_matches = sum(
        1 for req in optional if levels.get(req["skill_code"], 0) >= req["skill_level"]
    )
    title_rank = title_ranks[str(staff["title_code"])]
    total_level = sum(levels.values())
    return (
        preference_rank,
        assignment_count,
        0 if gap > 0 else 1,
        gap,
        title_rank,
        utilization,
        total_level - optional_matches,
        str(staff["code"]),
    )


def staff_can_fill(
    role_requirements: list[dict[str, Any]],
    levels: dict[str, int],
) -> bool:
    return all(
        levels.get(req["skill_code"], 0) >= req["skill_level"]
        for req in role_requirements
        if req["required"]
    )


def skill_gap(
    required: list[dict[str, Any]],
    levels: dict[str, int],
) -> int:
    return sum(
        max(0, req["skill_level"] - levels.get(req["skill_code"], 0))
        for req in required
    )


def period_codes_between(
    fiscal_periods: pd.DataFrame,
    start_period_code: str,
    end_period_code: str,
) -> list[str]:
    start = pd.Timestamp(start_period_code)
    end = pd.Timestamp(end_period_code)
    return [
        str(period["code"])
        for period in records(fiscal_periods.sort_values("start"))
        if start <= pd.Timestamp(period["start"]) <= end
    ]


def match_opportunity_assignments(
    pipeline_input: MatchAssignmentsInput,
) -> MatchAssignmentsOutput:
    requirements = role_skill_requirements(pipeline_input.role_skills)
    levels_by_staff = staff_skill_levels(pipeline_input.staff_career)
    staff_rows = records(pipeline_input.staffs)
    title_ranks = title_rank_map(pipeline_input.titles)
    preference_ranks = preference_rank_map(pipeline_input.staff_preference_options)
    utilization: dict[tuple[str, str], int] = {}
    assignments: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    assignment_sequence = 1
    assignment_counts: dict[str, int] = {}
    standard_assignments_by_opportunity: dict[str, set[str]] = {}

    request_rows = sorted(
        records(pipeline_input.requests),
        key=lambda request: request_priority(request, requirements),
    )

    for request in request_rows:
        request_code = str(request["code"])
        opportunity_code = str(request["opportunity_code"])
        period_code = str(request["start_period_code"])
        request_period_codes = period_codes_between(
            pipeline_input.fiscal_periods,
            str(request["start_period_code"]),
            str(request["end_period_code"]),
        )
        role_code = str(request["role_code"])
        required_headcount = int(request["headcount"])
        training_slots = max(0, int(request.get("training_slots", 0)))
        standard_headcount = required_headcount
        training_max_skill_gap = max(0, int(request.get("training_max_skill_gap", 0)))
        allocation = int(request["allocation_percentage"])
        role_requirements = requirements.get(role_code, [])
        required = [req for req in role_requirements if req["required"]]
        optional = [req for req in role_requirements if not req["required"]]
        selected_staff: set[str] = set()

        for slot in range(standard_headcount):
            candidates = []
            for staff in staff_rows:
                staff_code = str(staff["code"])
                if staff_code in selected_staff:
                    continue
                current_utilization = max(
                    utilization.get((staff_code, request_period_code), 0)
                    for request_period_code in request_period_codes
                )
                levels = levels_by_staff.get(staff_code, {})
                if not staff_can_fill(role_requirements, levels):
                    continue
                if not capacity_available(
                    utilization,
                    staff_code,
                    request_period_codes,
                    allocation,
                ):
                    continue
                candidates.append(
                    (
                        candidate_score(
                            staff=staff,
                            required=required,
                            optional=optional,
                            levels=levels,
                            title_ranks=title_ranks,
                            utilization=current_utilization,
                            preference_rank=preference_ranks.get(
                                (staff_code, request_code),
                                0,
                            ),
                        ),
                        staff,
                    )
                )

            if not candidates:
                reason = standard_unassigned_reason(
                    staff_rows,
                    selected_staff,
                    role_requirements,
                    levels_by_staff,
                    utilization,
                    request_period_codes,
                    allocation,
                )
                trace.append(
                    {
                        "opportunity_request_code": request_code,
                        "role_code": role_code,
                        "slot": slot + 1,
                        "staff_code": "",
                        "assignment_type": "standard",
                        "status": "unassigned",
                        "reason": reason,
                        "allocation_percentage": allocation,
                        "period_code": period_code,
                        "period_count": len(request_period_codes),
                        "skill_gap": "",
                        "score": "",
                    }
                )
                continue

            score, staff = min(candidates, key=lambda item: item[0])
            staff_code = str(staff["code"])
            for request_period_code in request_period_codes:
                util_key = (staff_code, request_period_code)
                utilization[util_key] = utilization.get(util_key, 0) + allocation
            selected_staff.add(staff_code)
            standard_assignments_by_opportunity.setdefault(opportunity_code, set()).add(
                staff_code
            )
            assignment_code = f"ASN-{assignment_sequence:06d}"
            assignment_sequence += 1
            assignments.append(
                {
                    "code": assignment_code,
                    "staff_code": staff_code,
                    "opportunity_request_code": request_code,
                    "assignment_type": "standard",
                }
            )
            assignment_counts[staff_code] = assignment_counts.get(staff_code, 0) + 1
            trace.append(
                {
                    "opportunity_request_code": request_code,
                    "role_code": role_code,
                    "slot": slot + 1,
                    "staff_code": staff_code,
                    "assignment_type": "standard",
                    "status": "assigned",
                    "reason": "",
                    "allocation_percentage": allocation,
                    "period_code": period_code,
                    "period_count": len(request_period_codes),
                    "skill_gap": 0,
                    "score": repr(score),
                }
            )

        for training_slot in range(training_slots):
            slot = standard_headcount + training_slot
            candidates = []
            if not standard_assignments_by_opportunity.get(opportunity_code):
                trace.append(
                    {
                        "opportunity_request_code": request_code,
                        "role_code": role_code,
                        "slot": slot + 1,
                        "staff_code": "",
                        "assignment_type": "training",
                        "status": "unassigned",
                        "reason": "training_requires_opportunity_standard_assignment",
                        "allocation_percentage": allocation,
                        "period_code": period_code,
                        "period_count": len(request_period_codes),
                        "skill_gap": "",
                        "score": "",
                    }
                )
                continue

            for staff in staff_rows:
                staff_code = str(staff["code"])
                if staff_code in selected_staff:
                    continue
                current_utilization = max(
                    utilization.get((staff_code, request_period_code), 0)
                    for request_period_code in request_period_codes
                )
                levels = levels_by_staff.get(staff_code, {})
                gap = skill_gap(required, levels)
                if gap > training_max_skill_gap:
                    continue
                if not capacity_available(
                    utilization,
                    staff_code,
                    request_period_codes,
                    allocation,
                ):
                    continue
                candidates.append(
                    (
                        training_candidate_score(
                            staff=staff,
                            required=required,
                            optional=optional,
                            levels=levels,
                            title_ranks=title_ranks,
                            utilization=current_utilization,
                            assignment_count=assignment_counts.get(staff_code, 0),
                            preference_rank=preference_ranks.get(
                                (staff_code, request_code),
                                0,
                            ),
                        ),
                        gap,
                        staff,
                    )
                )

            if not candidates:
                reason = training_unassigned_reason(
                    staff_rows,
                    selected_staff,
                    required,
                    levels_by_staff,
                    utilization,
                    request_period_codes,
                    allocation,
                    training_max_skill_gap,
                )
                trace.append(
                    {
                        "opportunity_request_code": request_code,
                        "role_code": role_code,
                        "slot": slot + 1,
                        "staff_code": "",
                        "assignment_type": "training",
                        "status": "unassigned",
                        "reason": reason,
                        "allocation_percentage": allocation,
                        "period_code": period_code,
                        "period_count": len(request_period_codes),
                        "skill_gap": "",
                        "score": "",
                    }
                )
                continue

            score, gap, staff = min(candidates, key=lambda item: item[0])
            staff_code = str(staff["code"])
            for request_period_code in request_period_codes:
                util_key = (staff_code, request_period_code)
                utilization[util_key] = utilization.get(util_key, 0) + allocation
            selected_staff.add(staff_code)
            assignment_code = f"ASN-{assignment_sequence:06d}"
            assignment_sequence += 1
            assignments.append(
                {
                    "code": assignment_code,
                    "staff_code": staff_code,
                    "opportunity_request_code": request_code,
                    "assignment_type": "training",
                }
            )
            assignment_counts[staff_code] = assignment_counts.get(staff_code, 0) + 1
            trace.append(
                {
                    "opportunity_request_code": request_code,
                    "role_code": role_code,
                    "slot": slot + 1,
                    "staff_code": staff_code,
                    "assignment_type": "training",
                    "status": "assigned",
                    "reason": "",
                    "allocation_percentage": allocation,
                    "period_code": period_code,
                    "period_count": len(request_period_codes),
                    "skill_gap": gap,
                    "score": repr(score),
                }
            )

    assignment_df = OpportunityAssignment.data_frame(assignments)
    trace_df = MatchingTrace.data_frame(trace)
    utilization_df = StaffUtilization.data_frame(
        (
            {
                "staff_code": staff_code,
                "period_code": period_code,
                "utilization_percentage": used,
            }
            for (staff_code, period_code), used in sorted(utilization.items())
        ),
    )

    return MatchAssignmentsOutput(
        assignments=assignment_df,
        matching_trace=trace_df,
        staff_utilization=utilization_df,
    )
