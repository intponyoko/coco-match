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
from cocom.pipeline.propose_theme_solutions.pipeline import (
    run_propose_theme_solutions_from_payload,
)


def propose_opportunity_portfolio(request: PipelineRequest) -> AgentResponse:
    output = run_propose_theme_solutions_from_payload(request_payload(request))
    themes = output.tables["theme_recommendations"]
    knowledge_nodes = audit_frame(output, "knowledge_nodes")
    theme_candidates = audit_frame(output, "theme_candidates")
    explanations = [
        {
            "agent": "opportunity_portfolio",
            "table": "theme_recommendations",
            "row_code": str(row.get("sales_plan_code", "")),
            "title": str(row.get("theme", "")),
            "reason": (
                "SalesPlanの業界・売上目標に対して、過去案件のTheme/Solutionと"
                "観測売上を根拠にPortfolio候補を作成しました。"
            ),
            "evidence_case_ids": str(row.get("evidence_case_ids", "")),
            "score": float(row.get("theme_score", 0.0)),
        }
        for row in themes.to_dict("records")
    ]
    evidence_refs = evidence_from_nodes(
        knowledge_nodes,
        evidence_ids_from_frame(themes),
    )
    diagnostics = table_count_diagnostics(
        {
            **output.tables,
            "theme_candidates": audit_frame(output, "theme_candidates"),
        },
        ["theme_candidates", "theme_recommendations"],
    )
    review = run_review_agent(
        agent_name="opportunity_portfolio",
        instructions=(
            "You support Japanese HITL review for sales-plan-to-opportunity "
            "portfolio proposals. Explain why the proposed Theme/Solution "
            "portfolio is reasonable, cite grounding evidence when available, "
            "and return concise Japanese explanations and diagnostics."
        ),
        input_payload={
            "theme_recommendations": themes.to_dict("records"),
            "theme_candidates": theme_candidates.to_dict("records"),
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
            "agent": "opportunity_portfolio",
            "prompt_version": "opportunity_portfolio.v1",
            "retrieval_query": "industry + solution + historical project theme",
            **review.metadata,
        },
    )
