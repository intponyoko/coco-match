from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ProposeProjectRequestsInput:
    config: dict[str, Any]
    sales_plans: pd.DataFrame
    accounts: pd.DataFrame
    roles: pd.DataFrame
    titles: pd.DataFrame | None
    fiscal_periods: pd.DataFrame
    staffs: pd.DataFrame | None
    past_cases: pd.DataFrame
    past_case_roles: pd.DataFrame
    past_case_links: pd.DataFrame
    theme_recommendations: pd.DataFrame


@dataclass(frozen=True)
class ProposeProjectRequestsOutput:
    knowledge_nodes: pd.DataFrame
    knowledge_edges: pd.DataFrame
    account_recommendations: pd.DataFrame
    project_sizing_recommendations: pd.DataFrame
    request_recommendations: pd.DataFrame
    consistency_metrics: pd.DataFrame | None = None
    project_review_issues: pd.DataFrame | None = None
    retrieved_evidence_chunks: pd.DataFrame | None = None
    proposal_runs: pd.DataFrame | None = None
    proposal_diagnostics: pd.DataFrame | None = None
    proposal_metadata: dict[str, Any] | None = None
