from typing import Any

import pandas as pd

from cocom.pipeline.common.table import records
from cocom.pipeline.common.periods import allocate_int
from cocom.schema import ThemeRecommendation


DEFAULT_PORTFOLIO_COUNT = 20


def portfolio_count(sales_plans: pd.DataFrame) -> int:
    configured = sales_plans.attrs.get("annual_opportunity_count")
    if configured is not None:
        return max(1, int(configured))
    total_revenue = int(sales_plans["target_revenue"].sum())
    if total_revenue <= 0:
        return DEFAULT_PORTFOLIO_COUNT
    return max(8, min(30, round(total_revenue / 17_500_000)))


def counts_by_industry(sales_plans: pd.DataFrame, total_count: int) -> dict[str, int]:
    industry_revenues = sales_plans.groupby("industry_code")["target_revenue"].sum()
    raw = {
        str(industry): max(1, int(round(total_count * revenue / industry_revenues.sum())))
        for industry, revenue in industry_revenues.items()
    }
    while sum(raw.values()) > total_count:
        industry = max(raw, key=lambda key: raw[key])
        if raw[industry] <= 1:
            break
        raw[industry] -= 1
    while sum(raw.values()) < total_count:
        industry = max(
            raw,
            key=lambda key: float(industry_revenues.get(key, 0)) / raw[key],
        )
        raw[industry] += 1
    return raw


def select_theme_recommendations(
    sales_plans: pd.DataFrame,
    theme_candidates: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    industry_revenues = {
        str(industry): int(revenue)
        for industry, revenue in sales_plans.groupby("industry_code")[
            "target_revenue"
        ].sum().items()
    }
    industry_counts = counts_by_industry(sales_plans, portfolio_count(sales_plans))
    for industry_code, count in industry_counts.items():
        plan_candidates = theme_candidates[
            theme_candidates["sales_plan_code"] == f"PORT-CAND-{industry_code}"
        ].sort_values(
            ["similarity_score", "observed_revenue_mean"],
            ascending=[False, False],
        )
        selected = records(plan_candidates)[:count]
        if not selected:
            continue

        weights = {
            f"{index:02d}-{theme['theme']}": float(theme["similarity_score"])
            * float(theme["observed_revenue_mean"])
            for index, theme in enumerate(selected, start=1)
        }
        revenues = allocate_int(industry_revenues[industry_code], weights)
        for index, theme in enumerate(selected, start=1):
            portfolio_code = f"PORT-{industry_code}-{index:03d}"
            rows.append(
                {
                    "sales_plan_code": portfolio_code,
                    "industry_code": industry_code,
                    "theme_rank": index,
                    "theme": theme["theme"],
                    "solution_code": theme["solution_code"],
                    "planned_revenue": revenues[f"{index:02d}-{theme['theme']}"],
                    "evidence_case_ids": theme["evidence_case_ids"],
                    "theme_score": round(float(theme["similarity_score"]), 6),
                    "observed_revenue_mean": theme["observed_revenue_mean"],
                    "observed_duration_mean": theme["observed_duration_mean"],
                    "delivery_model": theme["delivery_model"],
                    "customer_pain": theme["customer_pain"],
                }
            )
    return ThemeRecommendation.data_frame(rows)
