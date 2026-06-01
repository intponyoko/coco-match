from typing import Any

import pandas as pd

from cocom.pipeline.common.table import records, split_tokens, stable_join
from cocom.schema import AccountRecommendation


def account_evidence(
    past_cases: pd.DataFrame,
    evidence_case_ids: str,
    account_code: str,
) -> str:
    evidence_ids = split_tokens(evidence_case_ids)
    rows = past_cases[
        (past_cases["case_id"].isin(evidence_ids))
        & (past_cases["account_code"] == account_code)
    ]
    if rows.empty:
        return evidence_case_ids
    return stable_join(rows["case_id"].astype(str).to_list())


def select_account_recommendations(
    theme_recommendations: pd.DataFrame,
    accounts: pd.DataFrame,
    past_cases: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    max_potential_by_industry = (
        accounts.groupby("industry_code")["revenue_potential"].max().to_dict()
    )
    for theme in records(theme_recommendations):
        industry_accounts = accounts[
            accounts["industry_code"] == theme["industry_code"]
        ].copy()
        if industry_accounts.empty:
            continue
        max_potential = max(
            1.0,
            float(max_potential_by_industry[str(theme["industry_code"])]),
        )
        industry_accounts["account_score"] = (
            industry_accounts["revenue_potential"].astype(float) / max_potential
        )
        industry_accounts = industry_accounts.sort_values(
            ["account_score", "revenue_potential"],
            ascending=[False, False],
        )
        account_rows = records(industry_accounts)
        if not account_rows:
            continue
        selected_index = (int(theme["theme_rank"]) - 1) % len(account_rows)
        account = account_rows[selected_index]
        account_code = str(account["code"])
        rows.append(
            {
                "sales_plan_code": theme["sales_plan_code"],
                "industry_code": theme["industry_code"],
                "theme_rank": int(theme["theme_rank"]),
                "account_rank": selected_index + 1,
                "account_code": account_code,
                "account_name": account["name"],
                "account_segment": account["segment"],
                "theme": theme["theme"],
                "solution_code": theme["solution_code"],
                "planned_revenue": int(theme["planned_revenue"]),
                "evidence_case_ids": account_evidence(
                    past_cases,
                    str(theme["evidence_case_ids"]),
                    account_code,
                ),
                "theme_score": theme["theme_score"],
                "account_score": round(float(account["account_score"]), 6),
                "observed_revenue_mean": theme["observed_revenue_mean"],
                "observed_duration_mean": theme["observed_duration_mean"],
                "delivery_model": theme["delivery_model"],
                "customer_pain": theme["customer_pain"],
            }
        )
    return AccountRecommendation.data_frame(rows)
