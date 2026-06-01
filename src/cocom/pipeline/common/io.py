from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pandera.pandas as pa


TableMap = dict[str, pd.DataFrame]
JsonRow = dict[str, Any]
JsonTableMap = dict[str, list[JsonRow]]
ApprovalMap = dict[str, dict[str, Any]]


@dataclass(frozen=True)
class PipelinePayload:
    tables: TableMap
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    approvals: ApprovalMap = field(default_factory=dict)


@dataclass(frozen=True)
class JsonPayload:
    tables: JsonTableMap
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    approvals: ApprovalMap = field(default_factory=dict)


def table_records(frame: pd.DataFrame) -> list[JsonRow]:
    if frame.empty:
        return []
    return frame.where(pd.notna(frame), None).to_dict("records")


def tables_to_records(tables: TableMap) -> JsonTableMap:
    return {name: table_records(frame) for name, frame in tables.items()}


def records_to_tables(tables: JsonTableMap) -> TableMap:
    return {name: pd.DataFrame(rows) for name, rows in tables.items()}


def payload_to_json(payload: PipelinePayload) -> JsonPayload:
    return JsonPayload(
        tables=tables_to_records(payload.tables),
        config=payload.config,
        metadata=payload.metadata,
        approvals=payload.approvals,
    )


def payload_from_json(payload: JsonPayload) -> PipelinePayload:
    return PipelinePayload(
        tables=records_to_tables(payload.tables),
        config=payload.config,
        metadata=payload.metadata,
        approvals=payload.approvals,
    )


def validate_table(
    schema: type[pa.DataFrameModel],
    frame: pd.DataFrame,
) -> pd.DataFrame:
    return schema.validate(frame)


def require_tables(tables: TableMap, names: list[str]) -> None:
    missing = [name for name in names if name not in tables]
    if missing:
        raise ValueError(f"Missing required tables: {', '.join(missing)}")


def is_table_approved(payload: PipelinePayload, table_name: str) -> bool:
    approval = payload.approvals.get(table_name, {})
    return approval.get("status") == "approved"


def require_approved_tables(payload: PipelinePayload, names: list[str]) -> None:
    require_tables(payload.tables, names)
    missing = [name for name in names if not is_table_approved(payload, name)]
    if missing:
        raise ValueError(
            "Tables must be approved before this pipeline can run: "
            + ", ".join(missing)
        )


def approve_tables(
    payload: PipelinePayload,
    table_names: list[str],
    actor: str = "system",
    comment: str = "",
) -> PipelinePayload:
    approvals = dict(payload.approvals)
    for table_name in table_names:
        approvals[table_name] = {
            "status": "approved",
            "actor": actor,
            "comment": comment,
        }
    return PipelinePayload(
        tables=payload.tables,
        config=payload.config,
        metadata=payload.metadata,
        approvals=approvals,
    )


def merged_config(default_config: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    from cocom.pipeline.common.config import merge_config

    return merge_config(default_config, patch)


def append_table_frame(
    tables: TableMap,
    table_name: str,
    frame: pd.DataFrame | None,
) -> pd.DataFrame | None:
    if frame is None:
        return tables.get(table_name)
    existing = tables.get(table_name)
    if existing is None or existing.empty:
        return frame
    if frame.empty:
        return existing
    return pd.concat([existing, frame], ignore_index=True)


def merged_output_tables(
    base_tables: TableMap,
    *,
    direct_tables: dict[str, pd.DataFrame | None] | None = None,
    appended_tables: dict[str, pd.DataFrame | None] | None = None,
) -> TableMap:
    tables = dict(base_tables)
    for name, frame in (direct_tables or {}).items():
        if frame is not None:
            tables[name] = frame
    for name, frame in (appended_tables or {}).items():
        merged = append_table_frame(base_tables, name, frame)
        if merged is not None:
            tables[name] = merged
    return tables


def audit_artifacts_metadata(
    current_metadata: dict[str, Any],
    *,
    audit_tables: dict[str, pd.DataFrame | None] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing_artifacts = dict(current_metadata.get("audit_artifacts", {}))
    for name, frame in (audit_tables or {}).items():
        if frame is None:
            continue
        existing_artifacts[name] = table_records(frame)
    return {
        **current_metadata,
        **(extra_metadata or {}),
        **({"audit_artifacts": existing_artifacts} if existing_artifacts else {}),
    }


def audit_rows(metadata: dict[str, Any], table_name: str) -> list[JsonRow]:
    audit = metadata.get("audit_artifacts", {})
    rows = audit.get(table_name, []) if isinstance(audit, dict) else []
    return list(rows) if isinstance(rows, list) else []
