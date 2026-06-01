from cocom.pipeline.common.base import StatelessPipeline
from cocom.pipeline.common.csv_io import read_csv, write_tables
from cocom.pipeline.common.io import PipelinePayload, approve_tables, require_approved_tables
from cocom.pipeline.common.paths import PipelinePaths, default_pipeline_paths
from .io import (
    FinalizeAssignmentsInput,
    FinalizeAssignmentsOutput,
)
from cocom.schema import OpportunityAssignment


def run_finalize_assignments(
    pipeline_input: FinalizeAssignmentsInput,
) -> FinalizeAssignmentsOutput:
    rows = []
    for sequence, recommendation in enumerate(
        pipeline_input.assignment_recommendations.to_dict("records"),
        start=1,
    ):
        rows.append(
            {
                "code": f"ASN-{sequence:06d}",
                "staff_code": recommendation["staff_code"],
                "opportunity_request_code": recommendation["opportunity_request_code"],
                "assignment_type": recommendation["assignment_type"],
            }
        )
    return FinalizeAssignmentsOutput(
        opportunity_assignments=OpportunityAssignment.data_frame(rows)
    )


class FinalizeAssignmentsPipeline(
    StatelessPipeline[FinalizeAssignmentsInput, FinalizeAssignmentsOutput]
):
    name = "finalize_assignments"

    def run(
        self,
        pipeline_input: FinalizeAssignmentsInput,
    ) -> FinalizeAssignmentsOutput:
        return run_finalize_assignments(pipeline_input)

    def input_from_payload(
        self,
        payload: PipelinePayload,
        paths: PipelinePaths | None = None,
    ) -> FinalizeAssignmentsInput:
        require_approved_tables(payload, ["assignment_recommendations"])
        return FinalizeAssignmentsInput(
            assignment_recommendations=payload.tables["assignment_recommendations"]
        )

    def output_to_payload(
        self,
        output: FinalizeAssignmentsOutput,
        base: PipelinePayload,
    ) -> PipelinePayload:
        return PipelinePayload(
            tables={
                **base.tables,
                "opportunity_assignments": output.opportunity_assignments,
            },
            config=base.config,
            metadata={
                **base.metadata,
                "stage": "assignments_finalized",
            },
            approvals=base.approvals,
        )


def run_finalize_assignments_from_payload(
    payload: PipelinePayload,
    paths: PipelinePaths | None = None,
) -> PipelinePayload:
    return FinalizeAssignmentsPipeline().run_from_payload(payload, paths)


def load_payload(paths: PipelinePaths | None = None) -> PipelinePayload:
    resolved_paths = paths or default_pipeline_paths()
    return approve_tables(
        PipelinePayload(
            tables={
                "assignment_recommendations": read_csv(
                    resolved_paths.planning_data_dir, "assignment_recommendations"
                ),
            }
        ),
        ["assignment_recommendations"],
        actor="csv",
        comment="Loaded from approved local CSV.",
    )


def main() -> None:
    paths = default_pipeline_paths()
    output = run_finalize_assignments_from_payload(load_payload(paths))
    write_tables(
        paths.planning_data_dir,
        {"opportunity_assignments": output.tables["opportunity_assignments"]},
    )
    print("Assignment finalization completed.")
    print(f"- opportunity_assignments: {len(output.tables['opportunity_assignments'])}")
