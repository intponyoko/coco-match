from cocom.api.schemas import PipelineRequest, PipelineResponse
from cocom.pipeline.common.io import (
    JsonPayload,
    PipelinePayload,
    payload_from_json,
    payload_to_json,
)


def request_to_payload(request: PipelineRequest) -> PipelinePayload:
    return payload_from_json(
        JsonPayload(
            tables=request.tables,
            config=request.config,
            metadata=request.metadata,
            approvals=request.approvals,
        )
    )


def payload_to_response(payload: PipelinePayload) -> PipelineResponse:
    json_payload = payload_to_json(payload)
    return PipelineResponse(
        tables=json_payload.tables,
        metadata=json_payload.metadata,
        approvals=json_payload.approvals,
    )
