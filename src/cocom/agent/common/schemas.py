from typing import Any

from pydantic import BaseModel, Field


class AgentEvidence(BaseModel):
    evidence_id: str
    title: str
    summary: str
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    tables: dict[str, list[dict[str, Any]]]
    explanations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[AgentEvidence] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AgentInsightRequest(BaseModel):
    tables: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = Field(default_factory=dict)
    stage: str
    focus: dict[str, Any] = Field(default_factory=dict)


class AgentInsightResponse(BaseModel):
    stage: str
    headline: str
    summary: str
    confidence_label: str = "review"
    confidence_score: float = 0.0
    rationale: list[dict[str, Any]] = Field(default_factory=list)
    watchouts: list[dict[str, Any]] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list)
    impact: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[AgentEvidence] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
