from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from cocom.pipeline.common.io import table_records
from cocom.pipeline.common.table import stable_join
from cocom.schema import RetrievedEvidenceChunk


def build_theme_solution_retrieval_chunks(
    *,
    theme_recommendations: pd.DataFrame,
    past_cases: pd.DataFrame,
) -> pd.DataFrame:
    case_index = {
        str(row.get("case_id", "")): row for row in table_records(past_cases)
    }
    rows: list[dict[str, Any]] = []
    for recommendation in table_records(theme_recommendations):
        target_code = target_code_for_theme(recommendation)
        for rank, case_id in enumerate(split_ids(recommendation.get("evidence_case_ids")), start=1):
            case = case_index.get(case_id, {})
            rows.append(
                chunk_row(
                    task_name="propose_theme_solutions",
                    target_table="theme_recommendations",
                    target_code=target_code,
                    evidence_id=case_id or f"offline-theme-{rank}",
                    evidence_type="past_case",
                    title=str(case.get("title", f"Past case {case_id or rank}")),
                    snippet=(
                        f"Theme {case.get('theme', '')}; pain {case.get('customer_pain', '')}; "
                        f"solution {case.get('solution_code', '')}; revenue {case.get('actual_revenue', '')}"
                    ).strip("; "),
                    score=float(recommendation.get("theme_score", 0.0)),
                    source=str(case.get("account_code", case_id or "offline")),
                    retrieval_rank=rank,
                )
            )
    return RetrievedEvidenceChunk.data_frame(rows)


def build_project_request_retrieval_chunks(
    *,
    account_recommendations: pd.DataFrame,
    project_sizing_recommendations: pd.DataFrame,
    request_recommendations: pd.DataFrame,
    past_cases: pd.DataFrame,
    past_case_roles: pd.DataFrame,
) -> pd.DataFrame:
    case_index = {
        str(row.get("case_id", "")): row for row in table_records(past_cases)
    }
    role_rows_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in table_records(past_case_roles):
        role_rows_by_case[str(row.get("case_id", ""))].append(row)

    rows: list[dict[str, Any]] = []
    for account in table_records(account_recommendations):
        target_code = target_code_for_account(account)
        evidence_ids = split_ids(account.get("evidence_case_ids"))
        for rank, case_id in enumerate(evidence_ids, start=1):
            case = case_index.get(case_id, {})
            rows.append(
                chunk_row(
                    task_name="propose_project_requests",
                    target_table="account_recommendations",
                    target_code=target_code,
                    evidence_id=case_id or f"offline-account-{rank}",
                    evidence_type="past_case",
                    title=str(case.get("title", f"Past case {case_id or rank}")),
                    snippet=(
                        f"Account {case.get('account_code', '')}; theme {case.get('theme', '')}; "
                        f"solution {case.get('solution_code', '')}; revenue {case.get('observed_revenue', '')}"
                    ).strip("; "),
                    score=float(account.get("account_score", account.get("theme_score", 0.0))),
                    source=str(case.get("account_code", case_id or "offline")),
                    retrieval_rank=rank,
                )
            )

    for project in table_records(project_sizing_recommendations):
        target_code = str(project.get("project_spec_code", ""))
        evidence_ids = split_ids(project.get("evidence_case_ids"))
        for rank, case_id in enumerate(evidence_ids, start=1):
            case = case_index.get(case_id, {})
            roles = role_rows_by_case.get(case_id, [])
            role_mix = ", ".join(sorted({str(item.get("role_code", "")) for item in roles if item.get("role_code")})) or "n/a"
            rows.append(
                chunk_row(
                    task_name="propose_project_requests",
                    target_table="project_sizing_recommendations",
                    target_code=target_code,
                    evidence_id=case_id or f"offline-project-{rank}",
                    evidence_type="past_case",
                    title=str(case.get("title", f"Past case {case_id or rank}")),
                    snippet=(
                        f"Account {case.get('account_code', '')}; duration {case.get('duration_months', '')}; "
                        f"delivery {case.get('delivery_model', '')}; roles {role_mix}"
                    ).strip("; "),
                    score=float(project.get("grounding_score", 0.0)),
                    source=str(case.get("account_code", case_id or "offline")),
                    retrieval_rank=rank,
                )
            )

    for request in table_records(request_recommendations):
        target_code = str(request.get("request_recommendation_code", ""))
        evidence_ids = split_ids(request.get("evidence_case_ids"))
        for rank, case_id in enumerate(evidence_ids, start=1):
            roles = [
                row for row in role_rows_by_case.get(case_id, [])
                if str(row.get("role_code", "")) == str(request.get("role_code", ""))
            ]
            role_row = roles[0] if roles else {}
            rows.append(
                chunk_row(
                    task_name="propose_project_requests",
                    target_table="request_recommendations",
                    target_code=target_code,
                    evidence_id=f"{case_id}:{request.get('role_code', '')}" if case_id else f"offline-request-{rank}",
                    evidence_type="role_evidence",
                    title=f"Role {request.get('role_code', '')} evidence",
                    snippet=(
                        f"Phase {role_row.get('phase', request.get('phase', ''))}; "
                        f"headcount {role_row.get('headcount', request.get('headcount', ''))}; "
                        f"allocation {role_row.get('allocation_percentage', request.get('allocation_percentage', ''))}%"
                    ),
                    score=float(request.get("grounding_score", 0.0)),
                    source=case_id or "offline",
                    retrieval_rank=rank,
                )
            )

    return RetrievedEvidenceChunk.data_frame(rows)


def build_assignment_option_retrieval_chunks(
    *,
    staff_preference_options: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for option in table_records(staff_preference_options):
        rows.append(
            chunk_row(
                task_name="propose_assignment_options",
                target_table="staff_preference_options",
                target_code=str(option.get("preference_option_code", "")),
                evidence_id=str(option.get("opportunity_request_code", option.get("preference_option_code", ""))),
                evidence_type="option_context",
                title=f"{option.get('opportunity_code', 'Opportunity')} / {option.get('role_code', 'Role')}",
                snippet=(
                    f"{option.get('assignment_type', '')}; skill gap {option.get('skill_gap', '')}; "
                    f"allocation {option.get('allocation_percentage', '')}%; {option.get('reason', '')}"
                ),
                score=float(option.get("score", 0.0)),
                source=str(option.get("staff_code", "offline")),
                retrieval_rank=1,
            )
        )
    return RetrievedEvidenceChunk.data_frame(rows)


def build_assignment_retrieval_chunks(
    *,
    assignment_recommendations: pd.DataFrame,
    matching_trace: pd.DataFrame,
    staff_utilization: pd.DataFrame,
    staff_preference_options: pd.DataFrame | None,
) -> pd.DataFrame:
    trace_by_request: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in table_records(matching_trace):
        trace_by_request[str(row.get("opportunity_request_code", ""))].append(row)

    preference_by_request_staff: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in table_records(staff_preference_options if staff_preference_options is not None else pd.DataFrame()):
        key = (str(row.get("opportunity_request_code", "")), str(row.get("staff_code", "")))
        preference_by_request_staff[key].append(row)

    utilization_by_staff: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in table_records(staff_utilization):
        utilization_by_staff[str(row.get("staff_code", ""))].append(row)

    rows: list[dict[str, Any]] = []
    for recommendation in table_records(assignment_recommendations):
        request_code = str(recommendation.get("opportunity_request_code", ""))
        staff_code = str(recommendation.get("staff_code", ""))
        traces = trace_by_request.get(request_code, [])
        preferences = preference_by_request_staff.get((request_code, staff_code), [])
        for rank, trace in enumerate(traces[:2], start=1):
            rows.append(
                chunk_row(
                    task_name="propose_assignments",
                    target_table="assignment_recommendations",
                    target_code=str(recommendation.get("assignment_recommendation_code", "")),
                    evidence_id=f"{request_code}:trace:{rank}",
                    evidence_type="matching_trace",
                    title=f"{trace.get('status', 'matching')} / {trace.get('role_code', 'role')}",
                    snippet=(
                        f"reason {trace.get('reason', '')}; skill gap {trace.get('skill_gap', '')}; "
                        f"allocation {trace.get('allocation_percentage', '')}%"
                    ),
                    score=max(0.0, 100.0 - float_or_zero(trace.get("skill_gap")) * 10.0),
                    source=staff_code or "offline",
                    retrieval_rank=rank,
                )
            )
        for rank, preference in enumerate(preferences[:1], start=1):
            rows.append(
                chunk_row(
                    task_name="propose_assignments",
                    target_table="assignment_recommendations",
                    target_code=str(recommendation.get("assignment_recommendation_code", "")),
                    evidence_id=f"{request_code}:preference:{rank}",
                    evidence_type="staff_preference",
                    title=f"Preference {preference.get('assignment_type', '')}",
                    snippet=str(preference.get("reason", "")),
                    score=float(preference.get("score", 0.0)),
                    source=staff_code or "offline",
                    retrieval_rank=rank + 2,
                )
            )
        utilization_rows = utilization_by_staff.get(staff_code, [])
        if utilization_rows:
            average_utilization = sum(float_or_zero(row.get("utilization_percentage")) for row in utilization_rows) / len(utilization_rows)
            rows.append(
                chunk_row(
                    task_name="propose_assignments",
                    target_table="assignment_recommendations",
                    target_code=str(recommendation.get("assignment_recommendation_code", "")),
                    evidence_id=f"{staff_code}:utilization",
                    evidence_type="staff_utilization",
                    title="Utilization profile",
                    snippet=f"Average utilization {average_utilization:.1f}% across {len(utilization_rows)} periods.",
                    score=max(0.0, 100.0 - average_utilization),
                    source=staff_code or "offline",
                    retrieval_rank=4,
                )
            )
    return RetrievedEvidenceChunk.data_frame(rows)


def chunk_row(
    *,
    task_name: str,
    target_table: str,
    target_code: str,
    evidence_id: str,
    evidence_type: str,
    title: str,
    snippet: str,
    score: float,
    source: str,
    retrieval_rank: int,
) -> dict[str, Any]:
    return {
        "task_name": task_name,
        "target_table": target_table,
        "target_code": target_code,
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "title": title,
        "snippet": snippet[:500],
        "score": round(score, 4),
        "source": source,
        "retrieval_rank": retrieval_rank,
    }


def split_ids(value: Any) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def float_or_zero(value: Any) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def target_code_for_theme(row: dict[str, Any]) -> str:
    return f"{row.get('sales_plan_code', '')}:{row.get('theme_rank', '')}"


def target_code_for_account(row: dict[str, Any]) -> str:
    return (
        f"{row.get('sales_plan_code', '')}:{row.get('theme_rank', '')}:"
        f"{row.get('account_rank', '')}"
    )


def sync_theme_recommendation_evidence(
    *,
    theme_recommendations: pd.DataFrame,
    retrieved_evidence_chunks: pd.DataFrame,
) -> pd.DataFrame:
    case_ids_by_target = grouped_case_ids(
        retrieved_evidence_chunks,
        target_table="theme_recommendations",
    )
    rows: list[dict[str, Any]] = []
    for recommendation in table_records(theme_recommendations):
        target_code = target_code_for_theme(recommendation)
        row = dict(recommendation)
        row["evidence_case_ids"] = stable_join(
            case_ids_by_target.get(
                target_code,
                split_ids(recommendation.get("evidence_case_ids")),
            )
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=list(theme_recommendations.columns))


def sync_project_request_evidence(
    *,
    account_recommendations: pd.DataFrame,
    project_sizing_recommendations: pd.DataFrame,
    request_recommendations: pd.DataFrame,
    retrieved_evidence_chunks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    account_case_ids = grouped_case_ids(
        retrieved_evidence_chunks,
        target_table="account_recommendations",
    )
    project_case_ids = grouped_case_ids(
        retrieved_evidence_chunks,
        target_table="project_sizing_recommendations",
    )
    request_case_ids = grouped_case_ids(
        retrieved_evidence_chunks,
        target_table="request_recommendations",
    )
    account_rows: list[dict[str, Any]] = []
    for recommendation in table_records(account_recommendations):
        row = dict(recommendation)
        row["evidence_case_ids"] = stable_join(
            account_case_ids.get(
                target_code_for_account(recommendation),
                split_ids(recommendation.get("evidence_case_ids")),
            )
        )
        account_rows.append(row)
    project_rows: list[dict[str, Any]] = []
    for project in table_records(project_sizing_recommendations):
        row = dict(project)
        row["evidence_case_ids"] = stable_join(
            project_case_ids.get(
                str(project.get("project_spec_code", "")),
                split_ids(project.get("evidence_case_ids")),
            )
        )
        project_rows.append(row)
    request_rows: list[dict[str, Any]] = []
    for request in table_records(request_recommendations):
        row = dict(request)
        row["evidence_case_ids"] = stable_join(
            request_case_ids.get(
                str(request.get("request_recommendation_code", "")),
                split_ids(request.get("evidence_case_ids")),
            )
        )
        request_rows.append(row)
    return (
        pd.DataFrame(account_rows, columns=list(account_recommendations.columns)),
        pd.DataFrame(project_rows, columns=list(project_sizing_recommendations.columns)),
        pd.DataFrame(request_rows, columns=list(request_recommendations.columns)),
    )


def grouped_case_ids(
    retrieved_evidence_chunks: pd.DataFrame,
    *,
    target_table: str,
) -> dict[str, list[str]]:
    by_target: dict[str, list[str]] = defaultdict(list)
    for row in table_records(retrieved_evidence_chunks):
        if str(row.get("target_table", "")) != target_table:
            continue
        case_id = case_id_from_reference(row.get("evidence_id")) or case_id_from_reference(
            row.get("source")
        )
        if not case_id:
            continue
        by_target[str(row.get("target_code", ""))].append(case_id)
    return {
        target_code: sorted(dict.fromkeys(case_ids))
        for target_code, case_ids in by_target.items()
    }


def case_id_from_reference(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.startswith("case:"):
        text = text[5:]
    return text.split(":", 1)[0].strip()
