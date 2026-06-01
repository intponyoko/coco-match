from dataclasses import dataclass
from typing import Any

import pandas as pd

@dataclass(frozen=True)
class CreateOpportunitiesInput:
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
    request_human_approval: bool | None = None
