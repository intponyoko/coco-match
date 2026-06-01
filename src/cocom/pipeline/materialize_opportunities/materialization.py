from typing import Any

import pandas as pd

from cocom.pipeline.common.table import records
from cocom.pipeline.common.periods import fiscal_period_end_code
from cocom.schema import Opportunity, OpportunityRecommendation


def opportunity_code(project_spec: dict[str, Any], sequence: int) -> str:
    return f"OPP-{sequence:06d}"


def opportunity_record(
    fiscal_periods: pd.DataFrame,
    project_spec: dict[str, Any],
    sequence: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    code = opportunity_code(project_spec, sequence)
    row = {
        "code": code,
        "sales_plan_code": project_spec["sales_plan_code"],
        "account_code": project_spec["account_code"],
        "solution_code": project_spec["solution_code"],
        "start_period_code": project_spec["start_period_code"],
        "end_period_code": fiscal_period_end_code(
            fiscal_periods,
            str(project_spec["start_period_code"]),
            int(project_spec["duration_months"]),
        ),
        "estimated_revenue": int(project_spec["estimated_revenue"]),
        "theme": project_spec["theme"],
        "customer_pain": project_spec["customer_pain"],
        "evidence_case_ids": project_spec["evidence_case_ids"],
        "grounding_score": round(float(project_spec["grounding_score"]), 4),
        "sizing_method": project_spec["sizing_method"],
        "delivery_model": project_spec["delivery_model"],
    }
    context = {
        "industry_code": project_spec["industry_code"],
        "project_spec_code": project_spec["project_spec_code"],
        "sales_plan_code": project_spec["sales_plan_code"],
        "opportunity_code": code,
        "account_code": project_spec["account_code"],
        "account_name": project_spec["account_name"],
        "account_segment": project_spec["account_segment"],
        "solution_code": project_spec["solution_code"],
        "start_period_code": project_spec["start_period_code"],
        "theme": project_spec["theme"],
        "customer_pain": project_spec["customer_pain"],
        "evidence_case_ids": project_spec["evidence_case_ids"],
        "grounding_score": float(project_spec["grounding_score"]),
        "delivery_model": project_spec["delivery_model"],
        "revenue_band": "sized",
        "estimated_revenue": int(project_spec["estimated_revenue"]),
        "duration_months": int(project_spec["duration_months"]),
        "project_training_allowed": bool(
            project_spec.get("project_training_allowed", True)
        ),
        "project_training_max_skill_gap": int(
            project_spec.get("project_training_max_skill_gap", 0)
        ),
    }
    recommendation = {
        "sales_plan_code": project_spec["sales_plan_code"],
        "account_code": project_spec["account_code"],
        "account_name": project_spec["account_name"],
        "account_segment": project_spec["account_segment"],
        "recommendation_code": project_spec["project_spec_code"],
        "retrieval_rank": sequence,
        "retrieval_score": round(float(project_spec["grounding_score"]), 4),
        "case_id": project_spec["evidence_case_ids"],
        "case_title": project_spec["theme"],
        "industry_code": project_spec["industry_code"],
        "solution_code": project_spec["solution_code"],
        "revenue_band": "sized",
        "estimated_revenue": int(project_spec["estimated_revenue"]),
        "duration_months": int(project_spec["duration_months"]),
        "business_theme": str(project_spec["theme"]),
        "customer_pain": str(project_spec["customer_pain"]),
        "evidence": str(project_spec["evidence_case_ids"]),
        "retrieval_tags": str(project_spec["theme"]),
        "theme": str(project_spec["theme"]),
        "sizing_method": str(project_spec["sizing_method"]),
        "delivery_model": str(project_spec["delivery_model"]),
    }
    return row, context, recommendation


def materialize_opportunities(
    sales_plans: pd.DataFrame,
    fiscal_periods: pd.DataFrame,
    project_specs: pd.DataFrame,
    request_human_approval: bool,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, int], pd.DataFrame]:
    if request_human_approval:
        return (
            Opportunity.empty(),
            [],
            {},
            OpportunityRecommendation.empty(),
        )

    opportunities: list[dict[str, Any]] = []
    opportunity_context: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    for sequence, project_spec in enumerate(records(project_specs), start=1):
        row, context, recommendation = opportunity_record(
            fiscal_periods,
            project_spec,
            sequence,
        )
        opportunities.append(row)
        opportunity_context.append(context)
        recommendations.append(recommendation)

    opportunity_df = Opportunity.data_frame(opportunities)
    period_opportunity_counts = {}
    if not opportunity_df.empty:
        period_opportunity_counts = (
            opportunity_df.groupby("start_period_code")["code"].count().to_dict()
        )
    return (
        opportunity_df,
        opportunity_context,
        {
            str(period): int(count)
            for period, count in period_opportunity_counts.items()
        },
        OpportunityRecommendation.data_frame(recommendations),
    )
