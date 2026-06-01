from typing import Any

from cocom.agent.common.azure_assist import run_review_agent
from cocom.agent.common.payload import (
    agent_response,
    audit_frame,
    request_payload,
    table_count_diagnostics,
)
from cocom.agent.common.schemas import AgentResponse
from cocom.api.schemas import PipelineRequest
from cocom.pipeline.propose_assignments.pipeline import (
    run_propose_assignments_from_payload,
)


def review_matching(request: PipelineRequest) -> AgentResponse:
    payload = request_payload(request)
    output = (
        payload
        if "assignment_recommendations" in payload.tables
        and (
            "matching_trace" in payload.tables
            or "matching_trace" in payload.metadata.get("audit_artifacts", {})
        )
        else run_propose_assignments_from_payload(payload)
    )
    trace = output.tables.get("matching_trace")
    if trace is None:
        trace = audit_frame(output, "matching_trace")
    utilization = output.tables.get("staff_utilization")
    if utilization is None:
        utilization = audit_frame(output, "staff_utilization")
    diagnostics: list[dict[str, Any]] = table_count_diagnostics(
        {
            **output.tables,
            "matching_trace": trace,
            "staff_utilization": utilization,
        },
        ["assignment_recommendations", "matching_trace", "staff_utilization"],
    )
    if trace is not None and not trace.empty:
        status_counts = trace["status"].astype(str).value_counts().to_dict()
        diagnostics.append({"kind": "matching_status_counts", "counts": status_counts})
    if utilization is not None and not utilization.empty:
        zero_staff_months = int((utilization["utilization_percentage"] == 0).sum())
        full_staff_months = int((utilization["utilization_percentage"] >= 100).sum())
        diagnostics.append(
            {
                "kind": "utilization_distribution",
                "zero_staff_months": zero_staff_months,
                "full_staff_months": full_staff_months,
                "average": float(utilization["utilization_percentage"].mean()),
            }
        )
    explanations = [
        {
            "agent": "matching_review",
            "title": "Matching review",
            "reason": (
                "Assignment recommendation、matching trace、staff utilizationを比較し、"
                "未割当・育成枠・高稼働を部署承認前に確認できるようにしました。"
            ),
        }
    ]
    review = run_review_agent(
        agent_name="matching_review",
        instructions=(
            "You support Japanese department-level matching approval. Explain "
            "unassigned requests, training assignments, utilization risks, and "
            "whether the recommendation should be approved or edited."
        ),
        input_payload={
            "assignment_recommendations": table_records(
                output.tables.get("assignment_recommendations")
            ),
            "matching_trace": trace.to_dict("records")
            if trace is not None
            else [],
            "staff_utilization": utilization.to_dict("records")
            if utilization is not None
            else [],
        },
        fallback_explanations=explanations,
        fallback_diagnostics=diagnostics,
    )
    return agent_response(
        output,
        explanations=review.explanations,
        diagnostics=review.diagnostics,
        metadata={
            "agent": "matching_review",
            "prompt_version": "matching_review.v1",
            **review.metadata,
        },
    )


def table_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    return frame.to_dict("records")
