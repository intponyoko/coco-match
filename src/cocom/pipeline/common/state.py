from dataclasses import dataclass
from enum import StrEnum


class PlanningStage(StrEnum):
    THEME_SOLUTION_PROPOSED = "theme_solution_proposed"
    THEME_SOLUTION_APPROVED = "theme_solution_approved"
    PROJECT_REQUEST_PROPOSED = "project_request_proposed"
    PROJECT_REQUEST_APPROVED = "project_request_approved"
    OPPORTUNITIES_MATERIALIZED = "opportunities_materialized"
    STAFF_PREFERENCES_COLLECTED = "staff_preferences_collected"
    ASSIGNMENTS_PROPOSED = "assignments_proposed"
    ASSIGNMENTS_FINALIZED = "assignments_finalized"


@dataclass(frozen=True)
class StageTransition:
    stage: PlanningStage
    next_stage: PlanningStage | None
    owner: str
    action: str
    description: str


WORKFLOW: tuple[StageTransition, ...] = (
    StageTransition(
        PlanningStage.THEME_SOLUTION_PROPOSED,
        PlanningStage.THEME_SOLUTION_APPROVED,
        "department",
        "approve_theme_solution",
        "Review, edit, approve, reject, or add Theme/Solution recommendations.",
    ),
    StageTransition(
        PlanningStage.THEME_SOLUTION_APPROVED,
        PlanningStage.PROJECT_REQUEST_PROPOSED,
        "system",
        "propose_project_requests",
        "Create Account, Project sizing, and Request recommendations from approved themes.",
    ),
    StageTransition(
        PlanningStage.PROJECT_REQUEST_PROPOSED,
        PlanningStage.PROJECT_REQUEST_APPROVED,
        "department",
        "approve_project_requests",
        "Review, edit, approve, reject, or add ProjectSpec and Request recommendations.",
    ),
    StageTransition(
        PlanningStage.PROJECT_REQUEST_APPROVED,
        PlanningStage.OPPORTUNITIES_MATERIALIZED,
        "system",
        "materialize_opportunities",
        "Materialize approved ProjectSpec and Request recommendations.",
    ),
    StageTransition(
        PlanningStage.OPPORTUNITIES_MATERIALIZED,
        PlanningStage.STAFF_PREFERENCES_COLLECTED,
        "individual",
        "collect_staff_preferences",
        "Collect staff interest, no-project preference, and training preference.",
    ),
    StageTransition(
        PlanningStage.STAFF_PREFERENCES_COLLECTED,
        PlanningStage.ASSIGNMENTS_PROPOSED,
        "system",
        "propose_assignments",
        "Run matching and propose assignments with trace and utilization.",
    ),
    StageTransition(
        PlanningStage.ASSIGNMENTS_PROPOSED,
        PlanningStage.ASSIGNMENTS_FINALIZED,
        "department",
        "finalize_assignments",
        "Approve, edit, or reject assignment recommendations and finalize assignments.",
    ),
    StageTransition(
        PlanningStage.ASSIGNMENTS_FINALIZED,
        None,
        "system",
        "complete",
        "Planning run is complete.",
    ),
)


def workflow_records() -> list[dict[str, str | None]]:
    return [
        {
            "stage": transition.stage.value,
            "next_stage": (
                transition.next_stage.value if transition.next_stage is not None else None
            ),
            "owner": transition.owner,
            "action": transition.action,
            "description": transition.description,
        }
        for transition in WORKFLOW
    ]
