import pandas as pd
from pathlib import Path

from cocom.pipeline.common.base import StatelessPipeline
from cocom.pipeline.common.csv_io import read_csv, read_tables, write_tables
from cocom.pipeline.common.io import (
    PipelinePayload,
    audit_artifacts_metadata,
    audit_rows,
    merged_output_tables,
    require_tables,
)
from cocom.pipeline.common.proposal import build_deterministic_proposal_artifacts
from cocom.pipeline.common.paths import PipelinePaths, default_pipeline_paths
from cocom.pipeline.common.retrieval import build_assignment_retrieval_chunks
from .greedy import match_opportunity_assignments
from .io import (
    MatchAssignmentsInput,
    MatchAssignmentsOutput,
    ProposeAssignmentsInput,
    ProposeAssignmentsOutput,
)
from cocom.schema import (
    AssignmentRecommendation,
)


REQUIRED_MATCHING_INPUTS = [
    "opportunity_requests",
    "role_skills",
    "staff_career",
    "staffs",
    "titles",
    "fiscal_periods",
]


def assignment_recommendations_from_trace(matching_trace):
    rows = []
    assigned_rows = [
        row
        for row in matching_trace.to_dict("records")
        if str(row.get("status", "")) == "assigned" and str(row.get("staff_code", ""))
    ]
    for sequence, row in enumerate(assigned_rows, start=1):
        rows.append(
            {
                "assignment_recommendation_code": f"AREC-{sequence:06d}",
                "staff_code": row["staff_code"],
                "opportunity_request_code": row["opportunity_request_code"],
                "slot": int(row.get("slot", sequence)),
                "assignment_type": row["assignment_type"],
                "matching_reason": "greedy_skill_capacity_match",
                "comment": "",
            }
        )
    return AssignmentRecommendation.data_frame(rows)


def run_propose_assignments(
    pipeline_input: ProposeAssignmentsInput,
) -> ProposeAssignmentsOutput:
    output = run_match_assignments(
        MatchAssignmentsInput(
            requests=pipeline_input.requests,
            role_skills=pipeline_input.role_skills,
            staff_career=pipeline_input.staff_career,
            staffs=pipeline_input.staffs,
            titles=pipeline_input.titles,
            fiscal_periods=pipeline_input.fiscal_periods,
            staff_preference_options=pipeline_input.staff_preference_options,
            output_dir=None,
        )
    )
    fallback_assignment_recommendations = assignment_recommendations_from_trace(
        output.matching_trace
    )
    retrieved_evidence_chunks = build_assignment_retrieval_chunks(
        assignment_recommendations=fallback_assignment_recommendations,
        matching_trace=output.matching_trace,
        staff_utilization=output.staff_utilization,
        staff_preference_options=pipeline_input.staff_preference_options,
    )
    artifacts = build_deterministic_proposal_artifacts(
        task_name="propose_assignments",
        prompt_version="propose_assignments.v1",
        input_tables={
            "opportunity_requests": pipeline_input.requests,
            "role_skills": pipeline_input.role_skills,
            "staff_career": pipeline_input.staff_career,
            "staffs": pipeline_input.staffs,
            "titles": pipeline_input.titles,
            "fiscal_periods": pipeline_input.fiscal_periods,
            "staff_preference_options": (
                pipeline_input.staff_preference_options
                if pipeline_input.staff_preference_options is not None
                else pd.DataFrame()
            ),
        },
        output_tables={
            "assignment_recommendations": fallback_assignment_recommendations,
            "matching_trace": output.matching_trace,
            "staff_utilization": output.staff_utilization,
            "retrieved_evidence_chunks": retrieved_evidence_chunks,
        },
        description=(
            "Deterministic proposal matched opportunity requests using greedy "
            "skill, capacity, and preference constraints."
        ),
    )
    return ProposeAssignmentsOutput(
        assignment_recommendations=fallback_assignment_recommendations,
        matching_trace=output.matching_trace,
        staff_utilization=output.staff_utilization,
        retrieved_evidence_chunks=retrieved_evidence_chunks,
        proposal_runs=artifacts.proposal_runs,
        proposal_diagnostics=artifacts.proposal_diagnostics,
        proposal_metadata=artifacts.proposal_metadata,
    )


class ProposeAssignmentsPipeline(
    StatelessPipeline[ProposeAssignmentsInput, ProposeAssignmentsOutput]
):
    name = "propose_assignments"

    def run(self, pipeline_input: ProposeAssignmentsInput) -> ProposeAssignmentsOutput:
        return run_propose_assignments(pipeline_input)

    def input_from_payload(
        self,
        payload: PipelinePayload,
        paths: PipelinePaths | None = None,
    ) -> ProposeAssignmentsInput:
        require_tables(payload.tables, REQUIRED_MATCHING_INPUTS)
        return ProposeAssignmentsInput(
            requests=payload.tables["opportunity_requests"],
            role_skills=payload.tables["role_skills"],
            staff_career=payload.tables["staff_career"],
            staffs=payload.tables["staffs"],
            titles=payload.tables["titles"],
            fiscal_periods=payload.tables["fiscal_periods"],
            staff_preference_options=payload.tables.get("staff_preference_options"),
        )

    def output_to_payload(
        self,
        output: ProposeAssignmentsOutput,
        base: PipelinePayload,
    ) -> PipelinePayload:
        return PipelinePayload(
            tables=merged_output_tables(
                base.tables,
                direct_tables={
                    "assignment_recommendations": output.assignment_recommendations,
                    "matching_trace": output.matching_trace,
                    "staff_utilization": output.staff_utilization,
                    "retrieved_evidence_chunks": output.retrieved_evidence_chunks,
                },
                appended_tables={
                    "proposal_runs": output.proposal_runs,
                    "proposal_diagnostics": output.proposal_diagnostics,
                },
            ),
            config=base.config,
            metadata=audit_artifacts_metadata(
                base.metadata,
                audit_tables={
                    "matching_trace": output.matching_trace,
                    "staff_utilization": output.staff_utilization,
                    "retrieved_evidence_chunks": output.retrieved_evidence_chunks,
                    "proposal_runs": output.proposal_runs,
                    "proposal_diagnostics": output.proposal_diagnostics,
                },
                extra_metadata={
                    **(output.proposal_metadata or {}),
                    "stage": "assignments_proposed",
                },
            ),
            approvals=base.approvals,
        )


def run_propose_assignments_from_payload(
    payload: PipelinePayload,
    paths: PipelinePaths | None = None,
) -> PipelinePayload:
    return ProposeAssignmentsPipeline().run_from_payload(payload, paths)


def run_match_assignments(
    pipeline_input: MatchAssignmentsInput,
) -> MatchAssignmentsOutput:
    return match_opportunity_assignments(pipeline_input)


def write_match_assignments_output(
    output_dir: Path,
    output: MatchAssignmentsOutput,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output.assignments.to_csv(output_dir / "opportunity_assignments.csv", index=False)
    output.matching_trace.to_csv(output_dir / "matching_trace.csv", index=False)
    output.staff_utilization.to_csv(output_dir / "staff_utilization.csv", index=False)


def load_payload(paths: PipelinePaths | None = None) -> PipelinePayload:
    resolved_paths = paths or default_pipeline_paths()
    return PipelinePayload(
        tables={
            "opportunity_requests": read_csv(
                resolved_paths.planning_data_dir, "opportunity_requests"
            ),
            **read_tables(
                resolved_paths.sample_data_dir,
                ["role_skills", "staff_career", "staffs", "titles", "fiscal_periods"],
            ),
            "staff_preference_options": read_csv(
                resolved_paths.planning_data_dir, "staff_preference_options"
            ),
        }
    )


def main() -> None:
    paths = default_pipeline_paths()
    output = run_propose_assignments_from_payload(load_payload(paths))
    matching_trace = pd.DataFrame(audit_rows(output.metadata, "matching_trace"))
    staff_utilization = pd.DataFrame(
        audit_rows(output.metadata, "staff_utilization")
    )
    retrieved_evidence_chunks = pd.DataFrame(
        audit_rows(output.metadata, "retrieved_evidence_chunks")
    )
    write_tables(
        paths.planning_data_dir,
        {
            "assignment_recommendations": output.tables[
                "assignment_recommendations"
            ],
            "matching_trace": matching_trace,
            "staff_utilization": staff_utilization,
            "retrieved_evidence_chunks": retrieved_evidence_chunks,
        },
    )
    print("Assignment proposal completed.")
    print(
        f"- assignment_recommendations: "
        f"{len(output.tables['assignment_recommendations'])}"
    )
    print(f"- matching_trace: {len(matching_trace)}")
    print(f"- staff_utilization: {len(staff_utilization)}")
