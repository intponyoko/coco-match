from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MaterializeOpportunitiesInput:
    config: dict[str, Any]
    sales_plans: pd.DataFrame
    accounts: pd.DataFrame
    roles: pd.DataFrame
    fiscal_periods: pd.DataFrame
    past_cases: pd.DataFrame
    past_case_roles: pd.DataFrame
    past_case_links: pd.DataFrame
    project_sizing_recommendations: pd.DataFrame
    request_recommendations: pd.DataFrame


@dataclass(frozen=True)
class MaterializeOpportunitiesOutput:
    opportunity_recommendations: pd.DataFrame
    opportunities: pd.DataFrame
    opportunity_requests: pd.DataFrame
    allocation_trace: pd.DataFrame
    opportunity_context: list[dict[str, Any]]
    period_opportunity_counts: dict[str, int]
