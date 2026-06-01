from typing import Any

import pandas as pd

from cocom.pipeline.common.proposal import build_deterministic_proposal_artifacts
from cocom.pipeline.common.base import StatelessPipeline
from cocom.pipeline.common.csv_io import read_csv, read_tables, write_tables
from cocom.pipeline.common.io import (
    PipelinePayload,
    audit_artifacts_metadata,
    audit_rows,
    merged_output_tables,
    require_tables,
)
from cocom.pipeline.common.paths import PipelinePaths, default_pipeline_paths
from cocom.pipeline.common.retrieval import build_assignment_option_retrieval_chunks
from cocom.pipeline.common.table import records
from cocom.pipeline.propose_assignments.greedy import (
    role_skill_requirements,
    skill_gap,
    staff_can_fill,
    staff_skill_levels,
)
from .io import (
    ProposeAssignmentOptionsInput,
    ProposeAssignmentOptionsOutput,
)


REQUIRED_OPTION_INPUTS = [
    "staffs",
    "opportunities",
    "opportunity_requests",
    "role_skills",
    "staff_career",
    "fiscal_periods",
]


def period_codes_between(
    fiscal_periods: pd.DataFrame,
    start_period_code: str,
    end_period_code: str,
) -> list[str]:
    start = pd.Timestamp(start_period_code)
    end = pd.Timestamp(end_period_code)
    return [
        str(period["code"])
        for period in records(fiscal_periods.sort_values("start"))
        if start <= pd.Timestamp(period["start"]) <= end
    ]


def opportunity_has_standard_mentor(
    requests: list[dict[str, Any]],
    requirements: dict[str, list[dict[str, Any]]],
    levels_by_staff: dict[str, dict[str, int]],
    staff_rows: list[dict[str, Any]],
) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for request in requests:
        opportunity_code = str(request["opportunity_code"])
        role_requirements = requirements.get(str(request["role_code"]), [])
        has_standard_candidate = any(
            staff_can_fill(role_requirements, levels_by_staff.get(str(staff["code"]), {}))
            for staff in staff_rows
        )
        result[opportunity_code] = result.get(opportunity_code, False) or has_standard_candidate
    return result


def option_reason(
    assignment_type: str,
    skill_gap_value: int,
    role_requirements: list[dict[str, Any]],
) -> str:
    required_count = sum(1 for req in role_requirements if bool(req["required"]))
    if assignment_type == "standard":
        return f"meets {required_count} required skills"
    return f"within training gap {skill_gap_value}"


def run_propose_assignment_options(
    pipeline_input: ProposeAssignmentOptionsInput,
) -> ProposeAssignmentOptionsOutput:
    opportunity_by_code = {
        str(row["code"]): row
        for row in records(pipeline_input.opportunities)
    }
    request_rows = records(pipeline_input.opportunity_requests)
    staff_rows = records(pipeline_input.staffs)
    requirements = role_skill_requirements(pipeline_input.role_skills)
    levels_by_staff = staff_skill_levels(pipeline_input.staff_career)
    mentor_by_opportunity = opportunity_has_standard_mentor(
        request_rows,
        requirements,
        levels_by_staff,
        staff_rows,
    )

    rows: list[dict[str, Any]] = []
    sequence = 1
    for request in request_rows:
        opportunity = opportunity_by_code.get(str(request["opportunity_code"]), {})
        role_code = str(request["role_code"])
        role_requirements = requirements.get(role_code, [])
        required = [req for req in role_requirements if bool(req["required"])]
        training_gap_limit = max(0, int(request.get("training_max_skill_gap", 0)))
        training_slots = max(0, int(request.get("training_slots", 0)))
        headcount = max(0, int(request.get("headcount", 0)))
        total_slots = headcount + training_slots
        has_training_slots = training_slots > 0
        period_codes = period_codes_between(
            pipeline_input.fiscal_periods,
            str(request["start_period_code"]),
            str(request["end_period_code"]),
        )

        for staff in staff_rows:
            staff_code = str(staff["code"])
            levels = levels_by_staff.get(staff_code, {})
            can_standard = staff_can_fill(role_requirements, levels)
            gap = skill_gap(required, levels)
            can_training = (
                has_training_slots
                and not can_standard
                and training_gap_limit > 0
                and gap <= training_gap_limit
                and bool(mentor_by_opportunity.get(str(request["opportunity_code"]), False))
            )
            if not can_standard and not can_training:
                continue

            assignment_type = "standard" if can_standard else "training"
            eligibility_status = "eligible" if can_standard else "training_eligible"
            for period_code in period_codes:
                rows.append(
                    {
                        "preference_option_code": f"POPT-{sequence:06d}",
                        "staff_code": staff_code,
                        "period_code": period_code,
                        "opportunity_code": request["opportunity_code"],
                        "opportunity_request_code": request["code"],
                        "role_code": role_code,
                        "assignment_type": assignment_type,
                        "eligibility_status": eligibility_status,
                        "skill_gap": gap,
                        "allocation_percentage": int(request["allocation_percentage"]),
                        "request_headcount": headcount,
                        "request_training_slots": training_slots,
                        "request_total_slots": total_slots,
                        "start_period_code": request["start_period_code"],
                        "end_period_code": request["end_period_code"],
                        "theme": opportunity.get("theme", ""),
                        "mentor_available": bool(
                            mentor_by_opportunity.get(str(request["opportunity_code"]), False)
                        ),
                        "score": max(0, 100 - gap * 10),
                        "reason": option_reason(assignment_type, gap, role_requirements),
                        "preference_status": "not_selected",
                        "comment": "",
                    }
                )
                sequence += 1
    fallback_options = pd.DataFrame(rows)
    retrieved_evidence_chunks = build_assignment_option_retrieval_chunks(
        staff_preference_options=fallback_options,
    )
    artifacts = build_deterministic_proposal_artifacts(
        task_name="propose_assignment_options",
        prompt_version="propose_assignment_options.v1",
        input_tables={
            "staffs": pipeline_input.staffs,
            "opportunities": pipeline_input.opportunities,
            "opportunity_requests": pipeline_input.opportunity_requests,
            "role_skills": pipeline_input.role_skills,
            "staff_career": pipeline_input.staff_career,
            "fiscal_periods": pipeline_input.fiscal_periods,
        },
        output_tables={
            "staff_preference_options": fallback_options,
            "retrieved_evidence_chunks": retrieved_evidence_chunks,
        },
        description=(
            "Deterministic proposal generated staff preference options from skill "
            "requirements, staff careers, and opportunity requests."
        ),
    )
    return ProposeAssignmentOptionsOutput(
        staff_preference_options=fallback_options,
        retrieved_evidence_chunks=retrieved_evidence_chunks,
        proposal_runs=artifacts.proposal_runs,
        proposal_diagnostics=artifacts.proposal_diagnostics,
        proposal_metadata=artifacts.proposal_metadata,
    )


class ProposeAssignmentOptionsPipeline(
    StatelessPipeline[
        ProposeAssignmentOptionsInput,
        ProposeAssignmentOptionsOutput,
    ]
):
    name = "propose_assignment_options"

    def run(
        self,
        pipeline_input: ProposeAssignmentOptionsInput,
    ) -> ProposeAssignmentOptionsOutput:
        return run_propose_assignment_options(pipeline_input)

    def input_from_payload(
        self,
        payload: PipelinePayload,
        paths: PipelinePaths | None = None,
    ) -> ProposeAssignmentOptionsInput:
        require_tables(payload.tables, REQUIRED_OPTION_INPUTS)
        return ProposeAssignmentOptionsInput(
            staffs=payload.tables["staffs"],
            opportunities=payload.tables["opportunities"],
            opportunity_requests=payload.tables["opportunity_requests"],
            role_skills=payload.tables["role_skills"],
            staff_career=payload.tables["staff_career"],
            fiscal_periods=payload.tables["fiscal_periods"],
        )

    def output_to_payload(
        self,
        output: ProposeAssignmentOptionsOutput,
        base: PipelinePayload,
    ) -> PipelinePayload:
        return PipelinePayload(
            tables=merged_output_tables(
                base.tables,
                direct_tables={
                    "staff_preference_options": output.staff_preference_options,
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
                    "retrieved_evidence_chunks": output.retrieved_evidence_chunks,
                    "proposal_runs": output.proposal_runs,
                    "proposal_diagnostics": output.proposal_diagnostics,
                },
                extra_metadata={
                    **(output.proposal_metadata or {}),
                    "stage": "staff_preference_options_proposed",
                },
            ),
            approvals=base.approvals,
        )


def run_propose_assignment_options_from_payload(
    payload: PipelinePayload,
    paths: PipelinePaths | None = None,
) -> PipelinePayload:
    return ProposeAssignmentOptionsPipeline().run_from_payload(payload, paths)


def load_payload(paths: PipelinePaths | None = None) -> PipelinePayload:
    resolved_paths = paths or default_pipeline_paths()
    return PipelinePayload(
        tables={
            **read_tables(
                resolved_paths.sample_data_dir,
                ["staffs", "role_skills", "staff_career", "fiscal_periods"],
            ),
            "opportunities": read_csv(resolved_paths.planning_data_dir, "opportunities"),
            "opportunity_requests": read_csv(
                resolved_paths.planning_data_dir, "opportunity_requests"
            ),
        }
    )


def main() -> None:
    paths = default_pipeline_paths()
    output = run_propose_assignment_options_from_payload(load_payload(paths))
    retrieved_evidence_chunks = pd.DataFrame(
        audit_rows(output.metadata, "retrieved_evidence_chunks")
    )
    write_tables(
        paths.planning_data_dir,
        {
            "staff_preference_options": output.tables["staff_preference_options"],
            "retrieved_evidence_chunks": retrieved_evidence_chunks,
        },
    )
    print("Assignment option proposal completed.")
    print(f"- staff_preference_options: {len(output.tables['staff_preference_options'])}")
