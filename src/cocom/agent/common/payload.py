from collections.abc import Iterable
from hashlib import sha256
from typing import Any

import pandas as pd

from cocom.agent.common.schemas import AgentEvidence, AgentResponse
from cocom.api.schemas import PipelineRequest
from cocom.api.serialization import request_to_payload
from cocom.pipeline.common.io import PipelinePayload, audit_rows, payload_to_json


def request_payload(request: PipelineRequest) -> PipelinePayload:
    return request_to_payload(request)


def agent_response(
    payload: PipelinePayload,
    *,
    explanations: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]] | None = None,
    evidence_refs: list[AgentEvidence] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentResponse:
    json_payload = payload_to_json(payload)
    return AgentResponse(
        tables=json_payload.tables,
        approvals=json_payload.approvals,
        explanations=explanations,
        diagnostics=diagnostics or [],
        evidence_refs=evidence_refs or [],
        metadata={
            "agent_mode": "offline_mock",
            "input_hash": input_hash(json_payload.tables),
            **json_payload.metadata,
            **(metadata or {}),
        },
    )


def input_hash(tables: dict[str, list[dict[str, Any]]]) -> str:
    table_counts = "|".join(
        f"{name}:{len(rows)}" for name, rows in sorted(tables.items())
    )
    return sha256(table_counts.encode("utf-8")).hexdigest()[:16]


def evidence_ids_from_frame(frame: pd.DataFrame, column: str = "evidence_case_ids") -> list[str]:
    if column not in frame.columns:
        return []
    ids: set[str] = set()
    for value in frame[column].dropna().astype(str):
        for item in value.split(";"):
            item = item.strip()
            if item:
                ids.add(item)
    return sorted(ids)


def table_count_diagnostics(tables: dict[str, pd.DataFrame], names: Iterable[str]) -> list[dict[str, Any]]:
    return [
        {"kind": "table_count", "table": name, "rows": int(len(tables.get(name, [])))}
        for name in names
    ]


def evidence_from_nodes(
    nodes: pd.DataFrame,
    evidence_ids: Iterable[str],
) -> list[AgentEvidence]:
    if nodes.empty or "node_id" not in nodes.columns:
        return []
    wanted = set(evidence_ids)
    refs: list[AgentEvidence] = []
    for row in nodes.to_dict("records"):
        node_id = str(row.get("node_id", ""))
        source = str(row.get("source", ""))
        node_type = str(row.get("node_type", ""))
        direct_match = node_id in wanted
        source_case_match = source in wanted and node_type == "past_case"
        if not direct_match and not source_case_match:
            continue
        refs.append(
            AgentEvidence(
                evidence_id=source or node_id,
                title=str(row.get("label", node_id)),
                summary=str(row.get("label", node_id)),
                source=source,
                metadata={"node_type": node_type},
            )
        )
    return refs


def audit_frame(payload: PipelinePayload, table_name: str) -> pd.DataFrame:
    return pd.DataFrame(audit_rows(payload.metadata, table_name))
