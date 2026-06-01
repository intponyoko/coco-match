"""Shared pipeline adapters and lightweight utilities."""

from cocom.pipeline.common.base import StatelessPipeline
from cocom.pipeline.common.config import load_config, merge_config
from cocom.pipeline.common.csv_io import read_csv, read_tables, write_tables
from cocom.pipeline.common.io import (
    ApprovalMap,
    JsonPayload,
    PipelinePayload,
    TableMap,
    approve_tables,
    is_table_approved,
    payload_from_json,
    payload_to_json,
    require_approved_tables,
    require_tables,
)
from cocom.pipeline.common.knowledge import read_past_case_data
from cocom.pipeline.common.paths import PipelinePaths, default_pipeline_paths
from cocom.pipeline.common.state import PlanningStage, workflow_records

__all__ = [
    "JsonPayload",
    "PipelinePaths",
    "PipelinePayload",
    "PlanningStage",
    "StatelessPipeline",
    "ApprovalMap",
    "TableMap",
    "approve_tables",
    "default_pipeline_paths",
    "is_table_approved",
    "load_config",
    "merge_config",
    "payload_from_json",
    "payload_to_json",
    "read_csv",
    "read_tables",
    "read_past_case_data",
    "require_approved_tables",
    "require_tables",
    "workflow_records",
    "write_tables",
]
