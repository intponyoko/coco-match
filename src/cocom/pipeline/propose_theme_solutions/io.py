from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ProposeThemeSolutionsInput:
    config: dict[str, Any]
    sales_plans: pd.DataFrame
    accounts: pd.DataFrame
    roles: pd.DataFrame
    fiscal_periods: pd.DataFrame
    past_cases: pd.DataFrame
    past_case_roles: pd.DataFrame
    past_case_links: pd.DataFrame


@dataclass(frozen=True)
class ProposeThemeSolutionsOutput:
    knowledge_nodes: pd.DataFrame
    knowledge_edges: pd.DataFrame
    theme_candidates: pd.DataFrame
    theme_recommendations: pd.DataFrame
    consistency_metrics: pd.DataFrame | None = None
    retrieved_evidence_chunks: pd.DataFrame | None = None
    proposal_runs: pd.DataFrame | None = None
    proposal_diagnostics: pd.DataFrame | None = None
    proposal_metadata: dict[str, Any] | None = None
