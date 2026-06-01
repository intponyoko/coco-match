from typing import Any

import pandas as pd

from cocom.pipeline.common.evidence_graph import build_case_knowledge_graph
from cocom.pipeline.common.table import records, stable_join
from cocom.schema import ThemeCandidate


def build_knowledge_graph(
    accounts: pd.DataFrame,
    past_cases: pd.DataFrame,
    past_case_roles: pd.DataFrame,
    past_case_links: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return build_case_knowledge_graph(
        accounts=accounts,
        past_cases=past_cases,
        past_case_roles=past_case_roles,
        past_case_links=past_case_links,
    )


def theme_similarity(
    industry_revenue: int,
    case: dict[str, Any],
) -> float:
    observed_revenue = int(case["observed_revenue"])
    target_revenue = max(1, industry_revenue)
    revenue_score = min(observed_revenue, target_revenue) / max(
        observed_revenue,
        target_revenue,
    )
    outcome_score = 1.0 if str(case.get("outcome", "won")) == "won" else 0.0
    return (revenue_score + outcome_score) / 2.0


def build_theme_candidates(
    sales_plans: pd.DataFrame,
    past_cases: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    industry_revenues = (
        sales_plans.groupby("industry_code")["target_revenue"].sum().to_dict()
    )
    for industry_code, industry_revenue in industry_revenues.items():
        candidates = past_cases[
            past_cases["industry_code"] == industry_code
        ].copy()
        if candidates.empty:
            candidates = past_cases.copy()
        candidates["similarity_score"] = candidates.apply(
            lambda row: theme_similarity(int(industry_revenue), row.to_dict()),
            axis=1,
        )
        candidates = candidates.sort_values(
            ["similarity_score", "observed_revenue"],
            ascending=[False, False],
        )
        grouped = candidates.groupby(["theme", "solution_code"], as_index=False).agg(
            evidence_case_ids=("case_id", lambda values: stable_join(list(values))),
            similarity_score=("similarity_score", "mean"),
            observed_revenue_mean=("observed_revenue", "mean"),
            observed_duration_mean=("duration_months", "mean"),
            delivery_model=("delivery_model", lambda values: sorted(set(values))[0]),
            customer_pain=("customer_pain", lambda values: stable_join(list(values))),
        )
        for row in records(grouped):
            row["sales_plan_code"] = f"PORT-CAND-{industry_code}"
            rows.append(row)
    return ThemeCandidate.data_frame(rows)
