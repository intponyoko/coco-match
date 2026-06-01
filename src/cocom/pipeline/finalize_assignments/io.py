from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FinalizeAssignmentsInput:
    assignment_recommendations: pd.DataFrame


@dataclass(frozen=True)
class FinalizeAssignmentsOutput:
    opportunity_assignments: pd.DataFrame
