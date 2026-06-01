from dataclasses import dataclass

import pandas as pd

from cocom.pipeline.common.csv_io import read_tables, write_tables
from cocom.pipeline.common.io import PipelinePayload, approve_tables, audit_rows
from cocom.pipeline.common.paths import PipelinePaths, default_pipeline_paths
from cocom.pipeline.finalize_assignments.pipeline import (
    run_finalize_assignments_from_payload,
)
from cocom.pipeline.materialize_opportunities.pipeline import (
    run_materialize_opportunities_from_payload,
)
from cocom.pipeline.propose_assignments.io import MatchAssignmentsOutput
from cocom.pipeline.propose_assignment_options.pipeline import (
    run_propose_assignment_options_from_payload,
)
from cocom.pipeline.propose_assignments.pipeline import (
    run_propose_assignments_from_payload,
    write_match_assignments_output,
)
from cocom.pipeline.propose_project_requests.pipeline import (
    run_propose_project_requests_from_payload,
)
from cocom.pipeline.propose_theme_solutions.pipeline import (
    run_propose_theme_solutions_from_payload,
)


@dataclass(frozen=True)
class RunAllInput:
    paths: PipelinePaths | None = None
    request_human_approval: bool | None = None


@dataclass(frozen=True)
class RunAllOutput:
    input_tables: dict[str, pd.DataFrame]
    opportunities: pd.DataFrame
    requests: pd.DataFrame
    allocation_trace: pd.DataFrame
    opportunity_recommendations: pd.DataFrame
    assignments: pd.DataFrame
    matching_trace: pd.DataFrame
    staff_utilization: pd.DataFrame


def auto_approve_tables(payload: PipelinePayload, table_names: list[str]) -> PipelinePayload:
    return approve_tables(
        payload,
        table_names,
        actor="system",
        comment="Auto-approved by run-all.",
    )


def run_all(pipeline_input: RunAllInput) -> RunAllOutput:
    output, artifacts = run_all_stateless(pipeline_input)
    paths = pipeline_input.paths or default_pipeline_paths()
    write_tables(
        paths.planning_data_dir,
        {
            "theme_recommendations": artifacts["theme"].tables[
                "theme_recommendations"
            ],
            "project_sizing_recommendations": artifacts["project"].tables[
                "project_sizing_recommendations"
            ],
            "request_recommendations": artifacts["project"].tables[
                "request_recommendations"
            ],
            "opportunities": artifacts["materialized"].tables["opportunities"],
            "opportunity_requests": artifacts["materialized"].tables[
                "opportunity_requests"
            ],
            "staff_preference_options": artifacts["preference"].tables[
                "staff_preference_options"
            ],
            "assignment_recommendations": artifacts["assignment"].tables[
                "assignment_recommendations"
            ],
            "knowledge_nodes": pd.DataFrame(
                audit_rows(artifacts["theme"].metadata, "knowledge_nodes")
            ),
            "knowledge_edges": pd.DataFrame(
                audit_rows(artifacts["theme"].metadata, "knowledge_edges")
            ),
            "project_knowledge_nodes": artifacts["project"].tables[
                "project_knowledge_nodes"
            ],
            "project_knowledge_edges": artifacts["project"].tables[
                "project_knowledge_edges"
            ],
            "theme_candidates": pd.DataFrame(
                audit_rows(artifacts["theme"].metadata, "theme_candidates")
            ),
            "account_recommendations": pd.DataFrame(
                audit_rows(artifacts["project"].metadata, "account_recommendations")
            ),
            "opportunity_recommendations": pd.DataFrame(
                audit_rows(
                    artifacts["materialized"].metadata,
                    "opportunity_recommendations",
                )
            ),
            "allocation_trace": pd.DataFrame(
                audit_rows(artifacts["materialized"].metadata, "allocation_trace")
            ),
        },
    )
    matching_output = MatchAssignmentsOutput(
        assignments=output.assignments,
        matching_trace=output.matching_trace,
        staff_utilization=output.staff_utilization,
    )
    write_match_assignments_output(paths.planning_data_dir, matching_output)
    return output


def run_all_stateless(
    pipeline_input: RunAllInput,
) -> tuple[RunAllOutput, dict[str, PipelinePayload]]:
    paths = pipeline_input.paths or default_pipeline_paths()
    input_payload = load_planning_input_payload(paths)
    input_tables = input_payload.tables

    theme_payload = run_propose_theme_solutions_from_payload(input_payload, paths=paths)
    if pipeline_input.request_human_approval is False:
        theme_payload = auto_approve_tables(theme_payload, ["theme_recommendations"])

    project_payload = run_propose_project_requests_from_payload(
        theme_payload,
        paths=paths,
    )
    if pipeline_input.request_human_approval is False:
        project_payload = auto_approve_tables(
            project_payload,
            ["project_sizing_recommendations", "request_recommendations"],
        )

    materialized_payload = run_materialize_opportunities_from_payload(
        project_payload,
        paths=paths,
    )

    preference_payload = run_propose_assignment_options_from_payload(
        materialized_payload,
        paths=paths,
    )

    assignment_payload = run_propose_assignments_from_payload(preference_payload)
    if pipeline_input.request_human_approval is False:
        assignment_payload = auto_approve_tables(
            assignment_payload,
            ["assignment_recommendations"],
        )
    finalized_payload = run_finalize_assignments_from_payload(assignment_payload)
    output = RunAllOutput(
        input_tables=input_tables,
        opportunities=materialized_payload.tables["opportunities"],
        requests=materialized_payload.tables["opportunity_requests"],
        allocation_trace=pd.DataFrame(
            audit_rows(materialized_payload.metadata, "allocation_trace")
        ),
        opportunity_recommendations=pd.DataFrame(
            audit_rows(materialized_payload.metadata, "opportunity_recommendations")
        ),
        assignments=finalized_payload.tables["opportunity_assignments"],
        matching_trace=pd.DataFrame(
            audit_rows(assignment_payload.metadata, "matching_trace")
        ),
        staff_utilization=pd.DataFrame(
            audit_rows(assignment_payload.metadata, "staff_utilization")
        ),
    )
    return output, {
        "input": input_payload,
        "theme": theme_payload,
        "project": project_payload,
        "materialized": materialized_payload,
        "preference": preference_payload,
        "assignment": assignment_payload,
        "finalized": finalized_payload,
    }


def load_planning_input_payload(paths: PipelinePaths) -> PipelinePayload:
    table_names = [
        "sales_plans",
        "accounts",
        "roles",
        "titles",
        "fiscal_periods",
        "role_skills",
        "staff_career",
        "staffs",
    ]
    return PipelinePayload(
        tables=read_tables(paths.sample_data_dir, table_names),
        metadata={"stage": "input_tables_loaded"},
    )


def main() -> None:
    output = run_all(RunAllInput(request_human_approval=False))

    print("Cocom pipeline completed.")
    print(f"- input_tables: {len(output.input_tables)}")
    print(f"- opportunity_recommendations: {len(output.opportunity_recommendations)}")
    print(f"- opportunities: {len(output.opportunities)}")
    print(f"- opportunity_requests: {len(output.requests)}")
    print(f"- opportunity_assignments: {len(output.assignments)}")
    print(f"- allocation_trace: {len(output.allocation_trace)}")
    print(f"- matching_trace: {len(output.matching_trace)}")
    print(f"- staff_utilization: {len(output.staff_utilization)}")


if __name__ == "__main__":
    main()
