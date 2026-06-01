from dataclasses import dataclass
from typing import Any

from cocom.agent.common.client import (
    AzureFoundryAgentClient,
    DeterministicAgentClient,
    default_agent_client,
)


@dataclass(frozen=True)
class ReviewAgentResult:
    explanations: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class InsightAgentResult:
    output: dict[str, Any]
    metadata: dict[str, Any]


def run_review_agent(
    *,
    agent_name: str,
    instructions: str,
    input_payload: dict[str, Any],
    fallback_explanations: list[dict[str, Any]],
    fallback_diagnostics: list[dict[str, Any]],
) -> ReviewAgentResult:
    client = default_agent_client()
    configured_mode = agent_mode(client)
    metadata = {
        "agent_provider": client.__class__.__name__,
        "agent_mode": configured_mode,
        "agent_fallback_used": False,
    }
    request_payload = {
        "task": agent_name,
        "tables": summarize_tables(input_payload),
    }
    if configured_mode == "offline_mock":
        request_payload["fallback_explanations"] = fallback_explanations[:8]
        request_payload["fallback_diagnostics"] = fallback_diagnostics[:8]
    try:
        output = client.complete_json(
            instructions=instructions,
            input_payload=request_payload,
            schema_name=f"{agent_name}_review",
            response_schema=review_response_schema(),
        )
    except Exception as exc:
        return ReviewAgentResult(
            explanations=fallback_explanations,
            diagnostics=[
                *fallback_diagnostics,
                {
                    "kind": "agent_fallback",
                    "reason": str(exc),
                },
            ],
            metadata={
                **metadata,
                "agent_mode": "offline_mock",
                "agent_fallback_used": True,
                "agent_error": str(exc),
            },
        )
    if configured_mode == "online_llm":
        explanations = output.get("explanations")
        diagnostics = output.get("diagnostics")
        if not isinstance(explanations, list) or not isinstance(diagnostics, list):
            return ReviewAgentResult(
                explanations=fallback_explanations,
                diagnostics=[
                    *fallback_diagnostics,
                    {
                        "kind": "agent_fallback",
                        "reason": "Agent output did not include structured review lists.",
                    },
                ],
                metadata={
                    **metadata,
                    "agent_mode": "offline_mock",
                    "agent_fallback_used": True,
                    "agent_error": "Agent output did not include structured review lists.",
                },
            )
    return ReviewAgentResult(
        explanations=list(
            output.get("explanations", fallback_explanations) or fallback_explanations
        ),
        diagnostics=list(
            output.get("diagnostics", fallback_diagnostics) or fallback_diagnostics
        ),
        metadata=metadata,
    )


def run_insight_agent(
    *,
    agent_name: str,
    instructions: str,
    input_payload: dict[str, Any],
    fallback_output: dict[str, Any],
    schema_name: str,
) -> InsightAgentResult:
    client = default_agent_client()
    configured_mode = agent_mode(client)
    metadata = {
        "agent_provider": client.__class__.__name__,
        "agent_mode": configured_mode,
        "agent_fallback_used": False,
    }
    request_payload = {
        "task": agent_name,
        "tables": summarize_tables(input_payload),
        "focus": input_payload.get("focus", {}),
    }
    if configured_mode == "offline_mock":
        request_payload["fallback_output"] = fallback_output
    try:
        output = client.complete_json(
            instructions=instructions,
            input_payload=request_payload,
            schema_name=schema_name,
            response_schema=insight_response_schema(),
        )
    except Exception as exc:
        return InsightAgentResult(
            output=fallback_output,
            metadata={
                **metadata,
                "agent_mode": "offline_mock",
                "agent_fallback_used": True,
                "agent_error": str(exc),
            },
        )
    if not isinstance(output, dict):
        return InsightAgentResult(
            output=fallback_output,
            metadata={
                **metadata,
                "agent_mode": "offline_mock",
                "agent_fallback_used": True,
                "agent_error": "Agent output was not a JSON object.",
            },
        )
    return InsightAgentResult(output=output, metadata=metadata)


def summarize_tables(input_payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name, rows in input_payload.items():
        if isinstance(rows, list):
            summary[name] = {
                "rows": len(rows),
                "sample": rows[:3],
            }
    return summary


def agent_mode(client: Any) -> str:
    if isinstance(client, AzureFoundryAgentClient):
        return "online_llm"
    if isinstance(client, DeterministicAgentClient):
        return "offline_mock"
    return "offline_mock"


def review_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "explanations": {
                "type": "array",
                "items": {"type": "object"},
            },
            "diagnostics": {
                "type": "array",
                "items": {"type": "object"},
            },
        },
        "required": ["explanations", "diagnostics"],
        "additionalProperties": False,
    }


def insight_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "stage": {"type": "string"},
            "headline": {"type": "string"},
            "summary": {"type": "string"},
            "confidence_label": {"type": "string"},
            "confidence_score": {"type": "number"},
            "rationale": {"type": "array", "items": {"type": "object"}},
            "watchouts": {"type": "array", "items": {"type": "object"}},
            "alternatives": {"type": "array", "items": {"type": "object"}},
            "suggested_actions": {"type": "array", "items": {"type": "object"}},
            "impact": {"type": "array", "items": {"type": "object"}},
            "evidence_refs": {"type": "array", "items": {"type": "object"}},
            "metadata": {"type": "object"},
        },
        "required": [
            "stage",
            "headline",
            "summary",
            "confidence_label",
            "confidence_score",
            "rationale",
            "watchouts",
            "alternatives",
            "suggested_actions",
            "impact",
            "evidence_refs",
            "metadata",
        ],
        "additionalProperties": False,
    }
