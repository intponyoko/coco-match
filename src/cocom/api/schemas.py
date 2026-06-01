from typing import Any

from pydantic import BaseModel, Field


class PipelineRequest(BaseModel):
    tables: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = Field(default_factory=dict)


class PipelineResponse(BaseModel):
    tables: dict[str, list[dict[str, Any]]]
    metadata: dict[str, Any] = Field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
