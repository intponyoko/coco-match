from cocom.agent.common.azure_assist import run_review_agent
from cocom.agent.common.payload import (
    agent_response,
    audit_frame,
    evidence_from_nodes,
    evidence_ids_from_frame,
    request_payload,
    table_count_diagnostics,
)
from cocom.agent.common.schemas import AgentResponse
from cocom.api.schemas import PipelineRequest
from cocom.pipeline.common.io import approve_tables, is_table_approved
from cocom.pipeline.propose_project_requests.pipeline import (
    run_propose_project_requests_from_payload,
)


def propose_project_requests(request: PipelineRequest) -> AgentResponse:
    payload = request_payload(request)
    if not is_table_approved(payload, "theme_recommendations"):
        payload = approve_tables(
            payload,
            ["theme_recommendations"],
            actor="agent",
            comment="Approved for project/request proposal simulation.",
        )
    output = run_propose_project_requests_from_payload(payload)
    specs = output.tables["project_sizing_recommendations"]
    requests = output.tables["request_recommendations"]
    account_recommendations = audit_frame(output, "account_recommendations")
    explanations = [
        {
            "agent": "project_requests",
            "table": "project_sizing_recommendations",
            "row_code": str(row.get("project_spec_code", "")),
            "title": str(row.get("theme", "")),
            "reason": (
                "承認済みTheme/Solutionに対して、類似案件のAccount、期間、規模、"
                "delivery modelを根拠にPJ候補を作成しました。"
            ),
            "evidence_case_ids": str(row.get("evidence_case_ids", "")),
            "score": float(row.get("grounding_score", 0.0)),
        }
        for row in specs.to_dict("records")
    ]
    knowledge_nodes = audit_frame(output, "project_knowledge_nodes")
    if knowledge_nodes.empty:
        knowledge_nodes = audit_frame(output, "knowledge_nodes")
    evidence_refs = evidence_from_nodes(
        knowledge_nodes,
        set(evidence_ids_from_frame(specs)) | set(evidence_ids_from_frame(requests)),
    )
    diagnostics = table_count_diagnostics(
        {
            **output.tables,
            "account_recommendations": account_recommendations,
        },
        [
            "account_recommendations",
            "project_sizing_recommendations",
            "request_recommendations",
        ],
    )
    review = run_review_agent(
        agent_name="project_requests",
        instructions=(
            "You support Japanese HITL review for project sizing and request "
            "design. Explain duration, revenue scale, role mix, headcount, "
            "allocation, and training slot risks based on grounding documents."
        ),
        input_payload={
            "project_sizing_recommendations": specs.to_dict("records"),
            "request_recommendations": requests.to_dict("records"),
        },
        fallback_explanations=explanations,
        fallback_diagnostics=diagnostics,
    )
    return agent_response(
        output,
        explanations=review.explanations,
        diagnostics=review.diagnostics,
        evidence_refs=evidence_refs,
        metadata={
            "agent": "project_requests",
            "prompt_version": "project_requests.v1",
            "retrieval_query": "approved theme + account + project size + role mix",
            **review.metadata,
        },
    )
