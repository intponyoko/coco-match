from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import pandas as pd

from cocom.agent.common.client import (
    AzureFoundryAgentClient,
    DeterministicAgentClient,
    default_agent_client,
)
from cocom.pipeline.common.proposal import proposal_input_hash as build_proposal_input_hash
from cocom.pipeline.common.io import table_records
from cocom.schema.axis import BaseModel
from cocom.schema import ProposalDiagnostic, ProposalRun


TableValidator = Callable[[list[dict[str, Any]]], pd.DataFrame]


class ProposalMode(StrEnum):
    ONLINE_LLM = "online_llm"
    OFFLINE_MOCK = "offline_mock"


@dataclass(frozen=True)
class PipelineTaskSpec:
    task_name: str
    prompt_version: str
    instructions: str
    validators: dict[str, TableValidator]


@dataclass(frozen=True)
class ProposalProvenance:
    run_id: str
    task_name: str
    mode: ProposalMode
    provider: str
    prompt_version: str
    input_hash: str
    fallback_used: bool
    created_at: str


@dataclass(frozen=True)
class ProposalEnvelope:
    tables: dict[str, pd.DataFrame]
    diagnostics: list[dict[str, Any]]
    provenance: ProposalProvenance

    def metadata(self) -> dict[str, Any]:
        return {
            "proposal_run_id": self.provenance.run_id,
            "proposal_task": self.provenance.task_name,
            "proposal_mode": self.provenance.mode.value,
            "proposal_provider": self.provenance.provider,
            "proposal_prompt_version": self.provenance.prompt_version,
            "proposal_input_hash": self.provenance.input_hash,
            "proposal_fallback_used": self.provenance.fallback_used,
        }

    def proposal_runs_frame(self) -> pd.DataFrame:
        return ProposalRun.data_frame(
            [
                {
                    "run_id": self.provenance.run_id,
                    "task_name": self.provenance.task_name,
                    "mode": self.provenance.mode.value,
                    "provider": self.provenance.provider,
                    "prompt_version": self.provenance.prompt_version,
                    "input_hash": self.provenance.input_hash,
                    "output_tables": ";".join(sorted(self.tables)),
                    "fallback_used": self.provenance.fallback_used,
                    "created_at": self.provenance.created_at,
                }
            ]
        )

    def proposal_diagnostics_frame(self) -> pd.DataFrame:
        rows = [
            {
                "run_id": self.provenance.run_id,
                "task_name": self.provenance.task_name,
                "kind": str(item.get("kind", "proposal_info")),
                "severity": str(item.get("severity", "info")),
                "description": str(item.get("description", item.get("reason", ""))),
            }
            for item in self.diagnostics
        ]
        if not rows:
            rows = [
                {
                    "run_id": self.provenance.run_id,
                    "task_name": self.provenance.task_name,
                    "kind": "proposal_info",
                    "severity": "info",
                    "description": "Proposal completed without additional diagnostics.",
                }
            ]
        return ProposalDiagnostic.data_frame(rows)


def run_table_proposal(
    *,
    spec: PipelineTaskSpec,
    input_tables: dict[str, pd.DataFrame],
    fallback_tables: dict[str, pd.DataFrame],
    retrieved_evidence_chunks: pd.DataFrame | None = None,
) -> ProposalEnvelope:
    client = default_agent_client()
    provider = client.__class__.__name__
    mode = proposal_mode(client)
    input_hash = build_proposal_input_hash(input_tables)
    created_at = datetime.now(timezone.utc).isoformat()
    run_id = f"{spec.task_name}-{input_hash[:8]}"
    fallback_used = False
    diagnostics: list[dict[str, Any]] = [
        {
            "kind": "proposal_mode",
            "severity": "info",
            "description": f"Proposal executed in {mode.value} using {provider}.",
        }
    ]

    output_table_specs = {
        name: {
            "columns": list(frame.columns),
            "target_rows": len(frame),
        }
        for name, frame in fallback_tables.items()
    }
    fallback_records = {
        name: table_records(frame) for name, frame in fallback_tables.items()
    }
    request_payload = {
        "task": spec.task_name,
        "prompt_version": spec.prompt_version,
        "input_tables": summarize_tables(input_tables),
        "output_table_specs": output_table_specs,
    }
    if mode == ProposalMode.OFFLINE_MOCK:
        request_payload["retrieved_evidence_chunks"] = (
            table_records(retrieved_evidence_chunks)[:80]
            if retrieved_evidence_chunks is not None
            else []
        )
        request_payload["fallback_tables"] = fallback_records
    elif retrieved_evidence_chunks is not None:
        request_payload["retrieval_seed_examples"] = table_records(
            retrieved_evidence_chunks
        )[:20]

    retrieval_instruction = ""
    if "retrieved_evidence_chunks" in fallback_tables:
        retrieval_instruction = (
            "\n\n"
            "When `retrieved_evidence_chunks` is part of the output, use the provided "
            "Knowledge/file_search evidence to populate it. In online mode, treat "
            "`retrieval_seed_examples` only as query hints, run Knowledge/file_search "
            "yourself, and return the actual retrieved chunks. Every primary "
            "recommendation row must be grounded in at least one retrieved chunk, and "
            "its `evidence_case_ids` must match the case ids returned in that table."
        )
    structure_instruction = (
        "\n\n"
        "Treat this as evidence-driven completion of an existing planning structure, "
        "not free-form idea generation. Preserve table coverage, preserve identifier "
        "and code fields, do not collapse rows, and do not invent unrelated rows. "
        "If evidence is weak, keep the row structure and explain the gap in `diagnostics`."
    )

    try:
        response_schema = build_response_schema(
            fallback_tables=fallback_tables,
            validators=spec.validators,
        )
        output = client.complete_json(
            instructions=(
                f"{spec.instructions}\n\n"
                "Return ONLY a JSON object with keys `tables` and optional `diagnostics`. "
                "`tables` must map each output table name to an array of row objects. "
                "Do not omit required columns."
                f"{structure_instruction}"
                f"{retrieval_instruction}"
            ),
            input_payload=request_payload,
            schema_name=f"{spec.task_name}_tables",
            response_schema=response_schema,
        )
        proposed_tables = output.get("tables")
        if not isinstance(proposed_tables, dict):
            raise RuntimeError("Table completion did not return a `tables` object.")
        normalized = normalize_tables(
            proposed_tables,
            fallback_tables,
            spec.validators,
            require_complete=mode == ProposalMode.ONLINE_LLM,
        )
        raw_diagnostics = output.get("diagnostics", [])
        if isinstance(raw_diagnostics, list):
            diagnostics.extend(
                item for item in raw_diagnostics if isinstance(item, dict)
            )
        if mode == ProposalMode.OFFLINE_MOCK:
            diagnostics.append(
                {
                    "kind": "proposal_mock",
                    "severity": "info",
                    "description": "Offline mock proposal returned normalized tables.",
                }
            )
    except Exception as exc:
        fallback_used = True
        normalized = fallback_tables
        diagnostics.append(
            {
                "kind": "proposal_fallback",
                "severity": "warning",
                "description": str(exc),
            }
        )

    return ProposalEnvelope(
        tables=normalized,
        diagnostics=diagnostics,
        provenance=ProposalProvenance(
            run_id=run_id,
            task_name=spec.task_name,
            mode=mode,
            provider=provider,
            prompt_version=spec.prompt_version,
            input_hash=input_hash,
            fallback_used=fallback_used,
            created_at=created_at,
        ),
    )


def proposal_mode(client: Any) -> ProposalMode:
    if isinstance(client, AzureFoundryAgentClient):
        return ProposalMode.ONLINE_LLM
    if isinstance(client, DeterministicAgentClient):
        return ProposalMode.OFFLINE_MOCK
    return ProposalMode.OFFLINE_MOCK


def normalize_tables(
    proposed_tables: dict[str, Any],
    fallback_tables: dict[str, pd.DataFrame],
    validators: dict[str, TableValidator],
    require_complete: bool = False,
) -> dict[str, pd.DataFrame]:
    normalized: dict[str, pd.DataFrame] = {}
    for name, fallback in fallback_tables.items():
        if require_complete and name not in proposed_tables:
            raise RuntimeError(f"Table completion did not return required table `{name}`.")
        rows = proposed_tables.get(name, table_records(fallback))
        if not isinstance(rows, list):
            if require_complete:
                raise RuntimeError(f"Table `{name}` was not returned as a row array.")
            rows = table_records(fallback)
        sanitized = [row for row in rows if isinstance(row, dict)]
        if require_complete and len(sanitized) != len(rows):
            raise RuntimeError(f"Table `{name}` contained non-object rows.")
        validator = validators.get(name)
        if validator is not None:
            normalized[name] = validator(sanitized)
            continue
        normalized[name] = pd.DataFrame(sanitized, columns=list(fallback.columns))
    return normalized


def summarize_tables(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    return {
        name: {
            "rows": len(frame),
            "columns": list(frame.columns),
            "sample": table_records(frame)[:3],
        }
        for name, frame in tables.items()
    }


def build_response_schema(
    *,
    fallback_tables: dict[str, pd.DataFrame],
    validators: dict[str, TableValidator],
) -> dict[str, Any]:
    table_properties = {
        name: {
            "type": "array",
            "items": row_json_schema_for_table(name, validators, frame),
            "minItems": len(frame),
            "maxItems": len(frame),
        }
        for name, frame in fallback_tables.items()
    }
    return {
        "type": "object",
        "properties": {
            "tables": {
                "type": "object",
                "properties": table_properties,
                "required": list(table_properties.keys()),
                "additionalProperties": False,
            },
            "diagnostics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string"},
                        "severity": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["kind", "severity", "description"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["tables"],
        "additionalProperties": False,
    }


def row_json_schema_for_table(
    name: str,
    validators: dict[str, TableValidator],
    fallback_frame: pd.DataFrame,
) -> dict[str, Any]:
    model = schema_model_from_validator(validators.get(name))
    if model is not None:
        return model.row_json_schema()
    return {
        "type": "object",
        "properties": {
            column: json_schema_for_dtype(str(fallback_frame[column].dtype))
            for column in fallback_frame.columns
        },
        "required": list(fallback_frame.columns),
        "additionalProperties": False,
    }


def schema_model_from_validator(
    validator: TableValidator | None,
) -> type[BaseModel] | None:
    if validator is None:
        return None
    model = getattr(validator, "__self__", None)
    if isinstance(model, type) and issubclass(model, BaseModel):
        return model
    return None


def json_schema_for_dtype(dtype_name: str) -> dict[str, Any]:
    lowered = dtype_name.lower()
    if "bool" in lowered:
        return {"type": "boolean"}
    if "int" in lowered:
        return {"type": "integer"}
    if "float" in lowered:
        return {"type": "number"}
    return {"type": "string"}
