from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MatchAssignmentsInput:
    requests: pd.DataFrame
    role_skills: pd.DataFrame
    staff_career: pd.DataFrame
    staffs: pd.DataFrame
    titles: pd.DataFrame
    fiscal_periods: pd.DataFrame
    staff_preference_options: pd.DataFrame | None = None
    output_dir: Path | None = None


@dataclass(frozen=True)
class MatchAssignmentsOutput:
    assignments: pd.DataFrame
    matching_trace: pd.DataFrame
    staff_utilization: pd.DataFrame


@dataclass(frozen=True)
class ProposeAssignmentsInput:
    requests: pd.DataFrame
    role_skills: pd.DataFrame
    staff_career: pd.DataFrame
    staffs: pd.DataFrame
    titles: pd.DataFrame
    fiscal_periods: pd.DataFrame
    staff_preference_options: pd.DataFrame | None = None


@dataclass(frozen=True)
class ProposeAssignmentsOutput:
    assignment_recommendations: pd.DataFrame
    matching_trace: pd.DataFrame
    staff_utilization: pd.DataFrame
    retrieved_evidence_chunks: pd.DataFrame | None = None
    proposal_runs: pd.DataFrame | None = None
    proposal_diagnostics: pd.DataFrame | None = None
    proposal_metadata: dict[str, Any] | None = None
