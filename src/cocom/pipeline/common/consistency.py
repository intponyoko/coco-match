from __future__ import annotations

from typing import Any

import pandas as pd

from cocom.pipeline.common.periods import allocate_int
from cocom.pipeline.common.table import records
from cocom.schema import ConsistencyMetric, ProjectReviewIssue


def enforce_theme_revenue_totals(
    sales_plans: pd.DataFrame,
    theme_recommendations: pd.DataFrame,
) -> pd.DataFrame:
    if theme_recommendations.empty:
        return theme_recommendations.copy()

    normalized = theme_recommendations.copy()
    revenue_by_industry = (
        sales_plans.groupby("industry_code")["target_revenue"].sum().to_dict()
    )
    for industry_code, target_revenue in revenue_by_industry.items():
        mask = normalized["industry_code"].astype(str) == str(industry_code)
        industry_rows = normalized[mask]
        if industry_rows.empty:
            continue
        weights = {
            index: theme_revenue_weight(row.to_dict())
            for index, row in industry_rows.iterrows()
        }
        allocated = allocate_int(int(target_revenue), weights)
        for index, planned_revenue in allocated.items():
            normalized.at[index, "planned_revenue"] = int(planned_revenue)
    return normalized


def build_project_review_issues(
    project_sizing_recommendations: pd.DataFrame,
    request_recommendations: pd.DataFrame,
) -> pd.DataFrame:
    request_rows = records(request_recommendations)
    requests_by_project: dict[str, list[dict[str, Any]]] = {}
    for row in request_rows:
        requests_by_project.setdefault(str(row.get("project_spec_code", "")), []).append(row)

    rows: list[dict[str, Any]] = []
    for project in records(project_sizing_recommendations):
        project_code = str(project.get("project_spec_code", ""))
        project_requests = requests_by_project.get(project_code, [])
        positive_requests = [
            row for row in project_requests if int(float(row.get("headcount", 0) or 0)) > 0
        ]
        if not project_requests:
            rows.append(
                issue_row(
                    project,
                    issue_kind="missing_requests",
                    severity="high",
                    summary="No request rows were generated for this project proposal.",
                )
            )
            continue
        if not positive_requests:
            rows.append(
                issue_row(
                    project,
                    issue_kind="non_positive_headcount",
                    severity="high",
                    summary="All generated request rows have non-positive headcount.",
                )
            )
    return ProjectReviewIssue.data_frame(rows)


def build_consistency_metrics(
    sales_plans: pd.DataFrame,
    theme_recommendations: pd.DataFrame,
    project_sizing_recommendations: pd.DataFrame | None = None,
    request_recommendations: pd.DataFrame | None = None,
    project_review_issues: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    sales_total = int(sales_plans["target_revenue"].sum()) if not sales_plans.empty else 0
    theme_total = int(theme_recommendations["planned_revenue"].sum()) if not theme_recommendations.empty else 0
    rows.append(
        metric_row(
            metric_scope="global",
            metric_name="theme_revenue_coverage",
            metric_value=theme_total,
            reference_value=sales_total,
            summary=f"Theme revenue {theme_total:,} against SalesPlan {sales_total:,}.",
        )
    )

    sales_industry = (
        sales_plans.groupby("industry_code")["target_revenue"].sum().to_dict()
        if not sales_plans.empty
        else {}
    )
    theme_industry = (
        theme_recommendations.groupby("industry_code")["planned_revenue"].sum().to_dict()
        if not theme_recommendations.empty
        else {}
    )
    for industry_code in sorted(set(sales_industry) | set(theme_industry)):
        target = int(sales_industry.get(industry_code, 0))
        actual = int(theme_industry.get(industry_code, 0))
        rows.append(
            metric_row(
                metric_scope=f"industry:{industry_code}",
                metric_name="theme_revenue_coverage",
                metric_value=actual,
                reference_value=target,
                summary=f"Industry {industry_code} theme revenue {actual:,} against target {target:,}.",
            )
        )

    if project_sizing_recommendations is not None:
        project_total = len(project_sizing_recommendations)
        rows.append(
            metric_row(
                metric_scope="global",
                metric_name="project_count",
                metric_value=float(project_total),
                reference_value=float(len(theme_recommendations)),
                summary=f"Generated {project_total} project proposals from {len(theme_recommendations)} themes.",
            )
        )

    if request_recommendations is not None:
        positive_requests = request_recommendations[
            request_recommendations["headcount"].fillna(0).astype(float) > 0
        ] if not request_recommendations.empty else request_recommendations
        rows.append(
            metric_row(
                metric_scope="global",
                metric_name="positive_request_count",
                metric_value=float(len(positive_requests)),
                reference_value=float(len(request_recommendations)),
                summary=f"Positive-headcount requests {len(positive_requests)} / {len(request_recommendations)}.",
            )
        )

    if project_review_issues is not None:
        rows.append(
            metric_row(
                metric_scope="global",
                metric_name="projects_needing_review",
                metric_value=float(len(project_review_issues)),
                reference_value=float(
                    len(project_sizing_recommendations)
                    if project_sizing_recommendations is not None
                    else 0
                ),
                summary=f"{len(project_review_issues)} projects need manual review.",
            )
        )

    return ConsistencyMetric.data_frame(rows)


def theme_revenue_weight(row: dict[str, Any]) -> float:
    score = float(row.get("theme_score", 0.0) or 0.0)
    observed_revenue = float(row.get("observed_revenue_mean", 0.0) or 0.0)
    planned_revenue = float(row.get("planned_revenue", 0.0) or 0.0)
    return max(planned_revenue, score * max(observed_revenue, 1.0), 1.0)


def metric_row(
    *,
    metric_scope: str,
    metric_name: str,
    metric_value: float,
    reference_value: float,
    summary: str,
) -> dict[str, Any]:
    delta_value = float(metric_value) - float(reference_value)
    if abs(delta_value) < 0.5:
        status = "ok"
    elif reference_value == 0 and metric_value > 0:
        status = "review"
    else:
        status = "review"
    return {
        "metric_scope": metric_scope,
        "metric_name": metric_name,
        "metric_value": float(metric_value),
        "reference_value": float(reference_value),
        "delta_value": float(delta_value),
        "status": status,
        "summary": summary,
    }


def issue_row(
    project: dict[str, Any],
    *,
    issue_kind: str,
    severity: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "project_spec_code": str(project.get("project_spec_code", "")),
        "sales_plan_code": str(project.get("sales_plan_code", "")),
        "theme": str(project.get("theme", "")),
        "account_name": str(project.get("account_name", project.get("account_code", ""))),
        "issue_kind": issue_kind,
        "severity": severity,
        "summary": summary,
    }
