from cocom.pipeline.common.csv_io import read_csv, read_tables, write_tables
from cocom.pipeline.common.base import StatelessPipeline
from cocom.pipeline.common.opportunity_inputs import (
    create_opportunities_input_from_payload,
)
from cocom.pipeline.common.opportunity_io import (
    CreateOpportunitiesInput,
)
from cocom.pipeline.common.paths import PipelinePaths
from cocom.pipeline.common.io import (
    PipelinePayload,
    approve_tables,
    audit_artifacts_metadata,
    audit_rows,
    require_approved_tables,
)
from cocom.pipeline.common.paths import default_pipeline_paths
from .io import (
    MaterializeOpportunitiesInput,
    MaterializeOpportunitiesOutput,
)
from .materialization import (
    materialize_opportunities,
)
from cocom.schema import AllocationTrace, OpportunityRequest


def empty_request_outputs() -> tuple:
    return OpportunityRequest.empty(), AllocationTrace.empty()


def requests_from_approved_recommendations(
    pipeline_input: CreateOpportunitiesInput,
    opportunity_context: list[dict],
    period_opportunity_counts: dict[str, int],
    request_recommendations,
) -> tuple:
    if request_recommendations.empty:
        return empty_request_outputs()

    context_by_project_spec = {
        str(context["project_spec_code"]): context for context in opportunity_context
    }
    requests: list[dict] = []
    trace: list[dict] = []
    sequence = 1
    for recommendation in request_recommendations.to_dict("records"):
        project_spec_code = str(recommendation["project_spec_code"])
        context = context_by_project_spec.get(project_spec_code)
        if context is None:
            continue
        request_code = f"REQ-{sequence:06d}"
        sequence += 1
        requests.append(
            {
                "code": request_code,
                "opportunity_code": context["opportunity_code"],
                "start_period_code": recommendation["start_period_code"],
                "end_period_code": recommendation["end_period_code"],
                "role_code": recommendation["role_code"],
                "allocation_percentage": int(recommendation["allocation_percentage"]),
                "headcount": int(recommendation["headcount"]),
                "training_slots": int(recommendation.get("training_slots", 0)),
                "training_max_skill_gap": int(
                    recommendation.get("training_max_skill_gap", 0)
                ),
                "phase": recommendation["phase"],
                "evidence_case_ids": recommendation["evidence_case_ids"],
                "grounding_score": round(float(recommendation["grounding_score"]), 4),
            }
        )
        trace.append(
            {
                "sales_plan_code": context["sales_plan_code"],
                "opportunity_code": context["opportunity_code"],
                "request_code": request_code,
                "account_code": context["account_code"],
                "industry_code": context["industry_code"],
                "solution_code": context["solution_code"],
                "case_id": recommendation["evidence_case_ids"],
                "revenue_band": context["revenue_band"],
                "role_code": recommendation["role_code"],
                "sales_plan_revenue": int(context["estimated_revenue"]),
                "capped_sales_plan_revenue": int(context["estimated_revenue"]),
                "period_opportunity_capacity": period_opportunity_counts.get(
                    str(context.get("start_period_code", "")),
                    0,
                ),
                "project_duration_months": int(context["duration_months"]),
                "delivery_phase": recommendation["phase"],
                "opportunity_revenue": int(context["estimated_revenue"]),
                "role_revenue": int(recommendation["role_revenue"]),
                "required_person_month": float(
                    recommendation["required_person_month"]
                ),
                "request_months": float(recommendation["request_months"]),
                "kg_headcount": int(recommendation["headcount"]),
                "headcount": int(recommendation["headcount"]),
                "training_slots": int(recommendation.get("training_slots", 0)),
                "project_training_max_skill_gap": int(
                    recommendation.get("project_training_max_skill_gap", 0)
                ),
                "role_phase_training_max_skill_gap": int(
                    recommendation.get("role_phase_training_max_skill_gap", 0)
                ),
                "training_max_skill_gap": int(
                    recommendation.get("training_max_skill_gap", 0)
                ),
                "allocation_percentage": int(recommendation["allocation_percentage"]),
                "evidence_case_ids": recommendation["evidence_case_ids"],
                "grounding_score": round(float(recommendation["grounding_score"]), 4),
            }
        )
    if not requests:
        return empty_request_outputs()
    return (
        OpportunityRequest.data_frame(requests),
        AllocationTrace.data_frame(trace),
    )


def run_materialize_approved_recommendations(
    pipeline_input: CreateOpportunitiesInput,
    project_specs,
    request_recommendations,
) -> MaterializeOpportunitiesOutput:
    (
        opportunities,
        opportunity_context,
        period_opportunity_counts,
        recommendations,
    ) = materialize_opportunities(
        sales_plans=pipeline_input.sales_plans,
        fiscal_periods=pipeline_input.fiscal_periods,
        project_specs=project_specs,
        request_human_approval=False,
    )
    requests, trace = requests_from_approved_recommendations(
        pipeline_input,
        opportunity_context,
        period_opportunity_counts,
        request_recommendations,
    )
    return MaterializeOpportunitiesOutput(
        opportunity_recommendations=recommendations,
        opportunities=opportunities,
        opportunity_requests=requests,
        allocation_trace=trace,
        opportunity_context=opportunity_context,
        period_opportunity_counts=period_opportunity_counts,
    )


def input_from_opportunity_input(
    pipeline_input: CreateOpportunitiesInput,
    project_sizing_recommendations,
    request_recommendations,
) -> MaterializeOpportunitiesInput:
    return MaterializeOpportunitiesInput(
        config=pipeline_input.config,
        sales_plans=pipeline_input.sales_plans,
        accounts=pipeline_input.accounts,
        roles=pipeline_input.roles,
        fiscal_periods=pipeline_input.fiscal_periods,
        past_cases=pipeline_input.past_cases,
        past_case_roles=pipeline_input.past_case_roles,
        past_case_links=pipeline_input.past_case_links,
        project_sizing_recommendations=project_sizing_recommendations,
        request_recommendations=request_recommendations,
    )


def run_materialize_opportunities(
    pipeline_input: MaterializeOpportunitiesInput,
) -> MaterializeOpportunitiesOutput:
    opportunity_input = CreateOpportunitiesInput(
        config=pipeline_input.config,
        sales_plans=pipeline_input.sales_plans,
        accounts=pipeline_input.accounts,
        roles=pipeline_input.roles,
        titles=None,
        fiscal_periods=pipeline_input.fiscal_periods,
        staffs=None,
        past_cases=pipeline_input.past_cases,
        past_case_roles=pipeline_input.past_case_roles,
        past_case_links=pipeline_input.past_case_links,
        request_human_approval=False,
    )
    return run_materialize_approved_recommendations(
        opportunity_input,
        pipeline_input.project_sizing_recommendations,
        pipeline_input.request_recommendations,
    )


class MaterializeOpportunitiesPipeline(
    StatelessPipeline[MaterializeOpportunitiesInput, MaterializeOpportunitiesOutput]
):
    name = "materialize_opportunities"

    def run(
        self,
        pipeline_input: MaterializeOpportunitiesInput,
    ) -> MaterializeOpportunitiesOutput:
        return run_materialize_opportunities(pipeline_input)

    def input_from_payload(
        self,
        payload: PipelinePayload,
        paths: PipelinePaths | None = None,
    ) -> MaterializeOpportunitiesInput:
        require_approved_tables(
            payload,
            ["project_sizing_recommendations", "request_recommendations"],
        )
        opportunity_input = create_opportunities_input_from_payload(
            payload,
            paths=paths,
            request_human_approval=False,
        )
        return input_from_opportunity_input(
            opportunity_input,
            payload.tables["project_sizing_recommendations"],
            payload.tables["request_recommendations"],
        )

    def output_to_payload(
        self,
        output: MaterializeOpportunitiesOutput,
        base: PipelinePayload,
    ) -> PipelinePayload:
        return PipelinePayload(
            tables={
                **base.tables,
                "opportunities": output.opportunities,
                "opportunity_requests": output.opportunity_requests,
            },
            config=base.config,
            metadata=audit_artifacts_metadata(
                base.metadata,
                audit_tables={
                    "opportunity_recommendations": output.opportunity_recommendations,
                    "allocation_trace": output.allocation_trace,
                },
                extra_metadata={"stage": "opportunities_materialized"},
            ),
            approvals=base.approvals,
        )


def run_materialize_opportunities_from_payload(
    payload: PipelinePayload,
    paths: PipelinePaths | None = None,
) -> PipelinePayload:
    return MaterializeOpportunitiesPipeline().run_from_payload(payload, paths)


def load_payload(paths: PipelinePaths | None = None) -> PipelinePayload:
    resolved_paths = paths or default_pipeline_paths()
    return approve_tables(
        PipelinePayload(
            tables={
                **read_tables(
                    resolved_paths.sample_data_dir,
                    ["sales_plans", "accounts", "roles", "fiscal_periods"],
                ),
                "project_sizing_recommendations": read_csv(
                    resolved_paths.planning_data_dir, "project_sizing_recommendations"
                ),
                "request_recommendations": read_csv(
                    resolved_paths.planning_data_dir, "request_recommendations"
                ),
            }
        ),
        ["project_sizing_recommendations", "request_recommendations"],
        actor="csv",
        comment="Loaded from approved local CSV.",
    )


def main() -> None:
    paths = default_pipeline_paths()
    output = run_materialize_opportunities_from_payload(load_payload(paths), paths=paths)
    opportunity_recommendations = pd.DataFrame(
        audit_rows(output.metadata, "opportunity_recommendations")
    )
    allocation_trace = pd.DataFrame(audit_rows(output.metadata, "allocation_trace"))
    write_tables(
        paths.planning_data_dir,
        {
            "opportunity_recommendations": opportunity_recommendations,
            "opportunities": output.tables["opportunities"],
            "opportunity_requests": output.tables["opportunity_requests"],
            "allocation_trace": allocation_trace,
        },
    )
    print("Opportunity materialization completed.")
    print(f"- opportunities: {len(output.tables['opportunities'])}")
    print(f"- opportunity_requests: {len(output.tables['opportunity_requests'])}")
    print(f"- allocation_trace: {len(allocation_trace)}")
