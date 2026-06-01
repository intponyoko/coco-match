from collections.abc import Callable
import os
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cocom.agent.career_plan import propose_career_plan
from cocom.agent.common.evidence import lookup_evidence
from cocom.agent.common.schemas import (
    AgentEvidence,
    AgentInsightRequest,
    AgentInsightResponse,
    AgentResponse,
)
from cocom.agent.matching_review import review_matching
from cocom.agent.opportunity_portfolio import propose_opportunity_portfolio
from cocom.agent.project_requests import propose_project_requests
from cocom.agent.workflow_insight import generate_workflow_insight
from cocom.api.schemas import HealthResponse, PipelineRequest, PipelineResponse
from cocom.api.serialization import payload_to_response, request_to_payload
from cocom.pipeline.finalize_assignments.pipeline import (
    run_finalize_assignments_from_payload,
)
from cocom.pipeline.materialize_opportunities.pipeline import (
    run_materialize_opportunities_from_payload,
)
from cocom.pipeline.common.io import PipelinePayload
from cocom.pipeline.common.state import workflow_records
from cocom.pipeline.propose_assignment_options.pipeline import (
    run_propose_assignment_options_from_payload,
)
from cocom.pipeline.propose_assignments.pipeline import run_propose_assignments_from_payload
from cocom.pipeline.propose_project_requests.pipeline import (
    run_propose_project_requests_from_payload,
)
from cocom.pipeline.propose_theme_solutions.pipeline import (
    run_propose_theme_solutions_from_payload,
)
from cocom.pipeline.run_all import RunAllInput, run_all_stateless


PipelineRunner = Callable[[PipelinePayload], PipelinePayload]


router = APIRouter()


@router.get("/health")
@router.get("/api/v1/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/pipeline/workflow")
@router.get("/api/v1/pipeline/workflow")
def workflow() -> dict[str, list[dict[str, str | None]]]:
    return {"workflow": workflow_records()}


@router.post("/agent/opportunity-portfolio/propose")
@router.post("/api/v1/agent/opportunity-portfolio/propose")
def agent_opportunity_portfolio(request: PipelineRequest) -> AgentResponse:
    try:
        return propose_opportunity_portfolio(request)
    except Exception as exc:
        raise pipeline_error(exc) from exc


@router.post("/agent/project-requests/propose")
@router.post("/api/v1/agent/project-requests/propose")
def agent_project_requests(request: PipelineRequest) -> AgentResponse:
    try:
        return propose_project_requests(request)
    except Exception as exc:
        raise pipeline_error(exc) from exc


@router.post("/agent/matching/review")
@router.post("/api/v1/agent/matching/review")
def agent_matching_review(request: PipelineRequest) -> AgentResponse:
    try:
        return review_matching(request)
    except Exception as exc:
        raise pipeline_error(exc) from exc


@router.post("/agent/career-plan/propose")
@router.post("/api/v1/agent/career-plan/propose")
def agent_career_plan(request: PipelineRequest) -> AgentResponse:
    try:
        return propose_career_plan(request)
    except Exception as exc:
        raise pipeline_error(exc) from exc


@router.get("/agent/evidence/{evidence_id}")
@router.get("/api/v1/agent/evidence/{evidence_id}")
def agent_evidence(evidence_id: str) -> AgentEvidence:
    try:
        return lookup_evidence(evidence_id)
    except Exception as exc:
        raise pipeline_error(exc) from exc


@router.post("/agent/insights")
@router.post("/api/v1/agent/insights")
def agent_insights(request: AgentInsightRequest) -> AgentInsightResponse:
    try:
        return generate_workflow_insight(request)
    except Exception as exc:
        raise pipeline_error(exc) from exc


PIPELINE_RUNNERS: dict[str, PipelineRunner] = {
    "propose-theme-solutions": run_propose_theme_solutions_from_payload,
    "propose-project-requests": run_propose_project_requests_from_payload,
    "materialize-opportunities": run_materialize_opportunities_from_payload,
    "propose-assignment-options": run_propose_assignment_options_from_payload,
    "propose-assignments": run_propose_assignments_from_payload,
    "finalize-assignments": run_finalize_assignments_from_payload,
}


for pipeline_name, pipeline_runner in PIPELINE_RUNNERS.items():

    def endpoint(
        request: PipelineRequest,
        runner: PipelineRunner = pipeline_runner,
    ) -> PipelineResponse:
        return run_endpoint(request, runner)

    endpoint.__name__ = pipeline_name.replace("-", "_")
    router.post(f"/pipeline/{pipeline_name}")(endpoint)
    router.post(f"/api/v1/pipeline/{pipeline_name}")(endpoint)


@router.post("/pipeline/run-all")
@router.post("/api/v1/pipeline/run-all")
def run_all_pipeline(request: PipelineRequest) -> PipelineResponse:
    try:
        output, artifacts = run_all_stateless(
            RunAllInput(request_human_approval=False)
        )
        return PipelineResponse(
            tables={
                **{
                    name: frame.to_dict("records")
                    for name, frame in output.input_tables.items()
                },
                "opportunities": output.opportunities.to_dict("records"),
                "opportunity_requests": output.requests.to_dict("records"),
                "opportunity_assignments": output.assignments.to_dict("records"),
            },
            metadata={
                "stage": "assignments_finalized",
                **artifacts["finalized"].metadata,
            },
            approvals=artifacts["finalized"].approvals,
        )
    except Exception as exc:
        raise pipeline_error(exc) from exc


def create_app() -> FastAPI:
    app = FastAPI(title="coco-match Pipeline API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    mount_static_app(app)
    return app


def cors_origins() -> list[str]:
    value = os.getenv("COCO_MATCH_CORS_ORIGINS", "").strip()
    if not value:
        return ["*"]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def mount_static_app(app: FastAPI) -> None:
    static_dir = Path(
        os.getenv(
            "COCO_MATCH_STATIC_DIR",
            str(Path(__file__).resolve().parents[3] / "apps" / "hitl-ringi" / "dist"),
        )
    )
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


def run_endpoint(request: PipelineRequest, runner: PipelineRunner) -> PipelineResponse:
    try:
        output = runner(request_to_payload(request))
        return payload_to_response(output)
    except Exception as exc:
        raise pipeline_error(exc) from exc


def pipeline_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": exc.__class__.__name__,
            "message": str(exc),
        },
    )


def main() -> None:
    uvicorn.run("cocom.api.app:app", host="0.0.0.0", port=8000, reload=False)


app = create_app()


if __name__ == "__main__":
    main()
