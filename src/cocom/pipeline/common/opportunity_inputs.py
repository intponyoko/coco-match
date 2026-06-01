from typing import Any

from cocom.pipeline.common.config import load_config
from cocom.pipeline.common.io import PipelinePayload, merged_config, require_tables
from cocom.pipeline.common.opportunity_io import (
    CreateOpportunitiesInput,
)
from cocom.pipeline.common.paths import PipelinePaths, default_pipeline_paths
from cocom.pipeline.common.knowledge import read_past_case_data


REQUIRED_OPPORTUNITY_INPUTS = [
    "sales_plans",
    "accounts",
    "roles",
    "fiscal_periods",
]


def create_opportunities_input_from_payload(
    payload: PipelinePayload,
    paths: PipelinePaths | None = None,
    request_human_approval: bool | None = None,
) -> CreateOpportunitiesInput:
    resolved_paths = paths or default_pipeline_paths()
    require_tables(payload.tables, REQUIRED_OPPORTUNITY_INPUTS)
    past_case_data = read_past_case_data(resolved_paths.knowledge_data_dir)
    config: dict[str, Any] = load_config(resolved_paths.opportunity_config_dir)
    if payload.config:
        config = merged_config(config, payload.config)
    return CreateOpportunitiesInput(
        config=config,
        sales_plans=payload.tables["sales_plans"],
        accounts=payload.tables["accounts"],
        roles=payload.tables["roles"],
        titles=payload.tables.get("titles"),
        fiscal_periods=payload.tables["fiscal_periods"],
        staffs=payload.tables.get("staffs"),
        past_cases=payload.tables.get("past_cases", past_case_data["past_cases"]),
        past_case_roles=payload.tables.get(
            "past_case_roles",
            past_case_data["past_case_roles"],
        ),
        past_case_links=payload.tables.get(
            "past_case_links",
            past_case_data["past_case_links"],
        ),
        request_human_approval=request_human_approval,
    )
