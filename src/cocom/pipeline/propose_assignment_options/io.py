from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ProposeAssignmentOptionsInput:
    staffs: pd.DataFrame
    opportunities: pd.DataFrame
    opportunity_requests: pd.DataFrame
    role_skills: pd.DataFrame
    staff_career: pd.DataFrame
    fiscal_periods: pd.DataFrame


@dataclass(frozen=True)
class ProposeAssignmentOptionsOutput:
    staff_preference_options: pd.DataFrame
    retrieved_evidence_chunks: pd.DataFrame | None = None
    proposal_runs: pd.DataFrame | None = None
    proposal_diagnostics: pd.DataFrame | None = None
    proposal_metadata: dict[str, Any] | None = None
