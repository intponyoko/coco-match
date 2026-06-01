from cocom.agent.common.table_completion import PipelineTaskSpec, run_table_proposal
from typing import Any

import pandas as pd

from cocom.pipeline.common.base import StatelessPipeline
from cocom.pipeline.common.csv_io import read_csv, read_tables, write_tables
from cocom.pipeline.common.opportunity_inputs import (
    create_opportunities_input_from_payload,
)
from cocom.pipeline.common.opportunity_io import (
    CreateOpportunitiesInput,
)
from cocom.pipeline.common.paths import PipelinePaths
from cocom.pipeline.common.io import (
    PipelinePayload,
    audit_artifacts_metadata,
    audit_rows,
    approve_tables,
    merged_output_tables,
    require_approved_tables,
)
from cocom.pipeline.common.paths import default_pipeline_paths
from cocom.pipeline.common.consistency import (
    build_consistency_metrics,
    build_project_review_issues,
)
from cocom.pipeline.common.evidence_graph import build_rag_knowledge_graph
from cocom.pipeline.common.retrieval import (
    build_project_request_retrieval_chunks,
    sync_project_request_evidence,
)
from .io import (
    ProposeProjectRequestsInput,
    ProposeProjectRequestsOutput,
)
from .account_selection import (
    select_account_recommendations,
)
from cocom.pipeline.common.periods import (
    allocate_int,
    fiscal_period_count,
)
from .project_sizing import size_project_specs
from .request_generation import (
    request_period_for_evidence,
    role_allocation_for_evidence,
    role_evidence_rows,
    role_headcount_for_evidence,
    role_mix_for_evidence,
    role_phase_for_evidence,
    role_phase_training_for_evidence,
    scaled_training_slots,
)
from cocom.schema import (
    AccountRecommendation,
    ProjectSizingRecommendation,
    RequestRecommendation,
    RetrievedEvidenceChunk,
)


def build_request_recommendations(
    pipeline_input: CreateOpportunitiesInput,
    project_specs: pd.DataFrame,
) -> pd.DataFrame:
    if project_specs.empty:
        return RequestRecommendation.empty()

    rows: list[dict[str, Any]] = []
    sequence = 1
    for project_spec in project_specs.to_dict("records"):
        evidence_ids = [
            case_id.strip()
            for case_id in str(project_spec["evidence_case_ids"]).split(";")
            if case_id.strip()
        ]
        evidence = ";".join(evidence_ids)
        role_mix = role_mix_for_evidence(pipeline_input.past_case_roles, evidence_ids)
        if not role_mix:
            continue
        role_headcount = role_headcount_for_evidence(
            pipeline_input.past_case_roles,
            evidence_ids,
            role_mix,
        )
        role_allocation = role_allocation_for_evidence(
            pipeline_input.past_case_roles,
            evidence_ids,
            role_mix,
        )
        role_training = role_phase_training_for_evidence(
            pipeline_input.past_case_roles,
            evidence_ids,
            role_mix,
        )
        project_training_allowed = bool(
            project_spec.get("project_training_allowed", True)
        )
        project_training_max_skill_gap = int(
            project_spec.get("project_training_max_skill_gap", 0)
        )
        estimated_revenue = int(project_spec["estimated_revenue"])
        duration_months = int(project_spec["duration_months"])
        role_revenues = allocate_int(estimated_revenue, role_mix)
        for role_code, role_revenue in role_revenues.items():
            evidence_rows = role_evidence_rows(
                pipeline_input.past_case_roles,
                evidence_ids,
                role_code,
            )
            phase_name = role_phase_for_evidence(evidence_rows)
            request_start_code, request_end_code = request_period_for_evidence(
                pipeline_input.fiscal_periods,
                evidence_rows,
                str(project_spec["start_period_code"]),
                duration_months,
            )
            request_months = max(
                1.0,
                float(
                    fiscal_period_count(
                        pipeline_input.fiscal_periods,
                        request_start_code,
                        request_end_code,
                    )
                ),
            )
            headcount = int(role_headcount.get(role_code, 1))
            allocation_percentage = int(role_allocation.get(role_code, 50))
            required_person_month = (
                headcount * allocation_percentage / 100 * request_months
            )
            training_slots, role_phase_training_max_skill_gap = role_training.get(
                role_code, (0, 0)
            )
            training_max_skill_gap = (
                min(project_training_max_skill_gap, int(role_phase_training_max_skill_gap))
                if project_training_allowed
                else 0
            )
            training_slots = scaled_training_slots(
                int(training_slots),
                int(headcount),
                role_revenue,
                required_person_month,
                training_max_skill_gap,
            )
            if training_max_skill_gap <= 0:
                training_slots = 0
            rows.append(
                {
                    "request_recommendation_code": f"RRC-{sequence:06d}",
                    "project_spec_code": project_spec["project_spec_code"],
                    "start_period_code": request_start_code,
                    "end_period_code": request_end_code,
                    "role_code": role_code,
                    "allocation_percentage": allocation_percentage,
                    "headcount": headcount,
                    "training_slots": training_slots,
                    "project_training_max_skill_gap": project_training_max_skill_gap,
                    "role_phase_training_max_skill_gap": int(
                        role_phase_training_max_skill_gap
                    ),
                    "training_max_skill_gap": int(training_max_skill_gap),
                    "phase": phase_name,
                    "role_revenue": role_revenue,
                    "required_person_month": required_person_month,
                    "request_months": request_months,
                    "evidence_case_ids": evidence,
                    "grounding_score": round(float(project_spec["grounding_score"]), 4),
                    "comment": "",
                }
            )
            sequence += 1
    return RequestRecommendation.data_frame(rows)


def run_scale_request_draft(
    pipeline_input: CreateOpportunitiesInput,
    theme_recommendations: pd.DataFrame,
) -> ProposeProjectRequestsOutput:
    account_recommendations = select_account_recommendations(
        theme_recommendations=theme_recommendations,
        accounts=pipeline_input.accounts,
        past_cases=pipeline_input.past_cases,
    )
    project_specs = size_project_specs(
        account_recommendations,
        pipeline_input.sales_plans,
        pipeline_input.fiscal_periods,
        pipeline_input.past_case_roles,
        pipeline_input.staffs,
    )
    request_recommendations = build_request_recommendations(
        pipeline_input,
        project_specs,
    )
    return ProposeProjectRequestsOutput(
        knowledge_nodes=pd.DataFrame(),
        knowledge_edges=pd.DataFrame(),
        account_recommendations=account_recommendations,
        project_sizing_recommendations=project_specs,
        request_recommendations=request_recommendations,
    )


def sanitize_request_recommendations(
    request_recommendations: pd.DataFrame,
) -> pd.DataFrame:
    if request_recommendations.empty:
        return request_recommendations.copy()
    sanitized = request_recommendations.copy()
    sanitized["headcount"] = sanitized["headcount"].fillna(0).astype(int)
    sanitized["training_slots"] = sanitized["training_slots"].fillna(0).astype(int)
    sanitized = sanitized[sanitized["headcount"] > 0].copy()
    sanitized.loc[:, "training_slots"] = sanitized["training_slots"].clip(lower=0)
    return sanitized


def rebuild_request_quantitative_fields_from_evidence(
    request_recommendations: pd.DataFrame,
    project_sizing_recommendations: pd.DataFrame,
    pipeline_input: ProposeProjectRequestsInput,
) -> pd.DataFrame:
    if request_recommendations.empty or project_sizing_recommendations.empty:
        return request_recommendations.copy()
    project_by_code = {
        str(row.get("project_spec_code", "")): row
        for row in project_sizing_recommendations.to_dict("records")
    }
    requests_by_project: dict[str, list[dict[str, Any]]] = {}
    for row in request_recommendations.to_dict("records"):
        project_spec_code = str(row.get("project_spec_code", ""))
        requests_by_project.setdefault(project_spec_code, []).append(row)

    repaired_rows: list[dict[str, Any]] = []
    for project_spec_code, request_rows in requests_by_project.items():
        project = project_by_code.get(project_spec_code)
        if not project:
            repaired_rows.extend(dict(row) for row in request_rows)
            continue
        role_codes = list(
            dict.fromkeys(
                str(row.get("role_code", "")).strip()
                for row in request_rows
                if str(row.get("role_code", "")).strip()
            )
        )
        if not role_codes:
            repaired_rows.extend(dict(row) for row in request_rows)
            continue
        project_evidence_ids = [
            case_id.strip()
            for case_id in str(project.get("evidence_case_ids", "")).split(";")
            if case_id.strip()
        ]
        request_evidence_ids: list[str] = []
        for row in request_rows:
            request_evidence_ids.extend(
                [
                    case_id.strip()
                    for case_id in str(row.get("evidence_case_ids", "")).split(";")
                    if case_id.strip()
                ]
            )
        evidence_ids = list(dict.fromkeys(request_evidence_ids or project_evidence_ids))
        if not evidence_ids:
            repaired_rows.extend(dict(row) for row in request_rows)
            continue
        evidence_role_mix = role_mix_for_evidence(
            pipeline_input.past_case_roles,
            evidence_ids,
        )
        filtered_role_mix = {
            role_code: float(evidence_role_mix.get(role_code, 0.0))
            for role_code in role_codes
            if float(evidence_role_mix.get(role_code, 0.0)) > 0
        }
        if not filtered_role_mix:
            equal_weight = 1.0 / max(len(role_codes), 1)
            filtered_role_mix = {
                role_code: equal_weight for role_code in role_codes
            }
        role_headcount = role_headcount_for_evidence(
            pipeline_input.past_case_roles,
            evidence_ids,
            filtered_role_mix,
        )
        role_allocation = role_allocation_for_evidence(
            pipeline_input.past_case_roles,
            evidence_ids,
            filtered_role_mix,
        )
        role_training = role_phase_training_for_evidence(
            pipeline_input.past_case_roles,
            evidence_ids,
            filtered_role_mix,
        )
        role_revenues = allocate_int(
            int(project.get("estimated_revenue", 0) or 0),
            filtered_role_mix,
        )
        duration_months = int(project.get("duration_months", 1) or 1)
        project_training_allowed = bool(project.get("project_training_allowed", True))
        project_training_max_skill_gap = int(
            project.get("project_training_max_skill_gap", 0) or 0
        )
        project_start_period_code = str(project.get("start_period_code", ""))

        for request in request_rows:
            row = dict(request)
            role_code = str(request.get("role_code", "")).strip()
            if not role_code:
                repaired_rows.append(row)
                continue
            evidence_rows = role_evidence_rows(
                pipeline_input.past_case_roles,
                evidence_ids,
                role_code,
            )
            phase_name = role_phase_for_evidence(evidence_rows)
            request_start_code, request_end_code = request_period_for_evidence(
                pipeline_input.fiscal_periods,
                evidence_rows,
                project_start_period_code,
                duration_months,
            )
            request_months = max(
                1.0,
                float(
                    fiscal_period_count(
                        pipeline_input.fiscal_periods,
                        request_start_code,
                        request_end_code,
                    )
                ),
            )
            headcount = int(role_headcount.get(role_code, 1))
            allocation_percentage = int(role_allocation.get(role_code, 50))
            role_revenue = int(role_revenues.get(role_code, 0))
            required_person_month = (
                headcount * allocation_percentage / 100 * request_months
            )
            training_slots, role_phase_training_max_skill_gap = role_training.get(
                role_code, (0, 0)
            )
            training_max_skill_gap = (
                min(project_training_max_skill_gap, int(role_phase_training_max_skill_gap))
                if project_training_allowed
                else 0
            )
            training_slots = scaled_training_slots(
                int(training_slots),
                int(headcount),
                role_revenue,
                required_person_month,
                training_max_skill_gap,
            )
            if training_max_skill_gap <= 0:
                training_slots = 0
            row.update(
                {
                    "start_period_code": request_start_code,
                    "end_period_code": request_end_code,
                    "allocation_percentage": allocation_percentage,
                    "headcount": headcount,
                    "training_slots": training_slots,
                    "project_training_max_skill_gap": project_training_max_skill_gap,
                    "role_phase_training_max_skill_gap": int(
                        role_phase_training_max_skill_gap
                    ),
                    "training_max_skill_gap": int(training_max_skill_gap),
                    "phase": phase_name,
                    "role_revenue": role_revenue,
                    "required_person_month": required_person_month,
                    "request_months": request_months,
                }
            )
            repaired_rows.append(row)
    return RequestRecommendation.data_frame(repaired_rows)


def input_from_opportunity_input(
    pipeline_input: CreateOpportunitiesInput,
    theme_recommendations: pd.DataFrame,
) -> ProposeProjectRequestsInput:
    return ProposeProjectRequestsInput(
        config=pipeline_input.config,
        sales_plans=pipeline_input.sales_plans,
        accounts=pipeline_input.accounts,
        roles=pipeline_input.roles,
        titles=pipeline_input.titles,
        fiscal_periods=pipeline_input.fiscal_periods,
        staffs=pipeline_input.staffs,
        past_cases=pipeline_input.past_cases,
        past_case_roles=pipeline_input.past_case_roles,
        past_case_links=pipeline_input.past_case_links,
        theme_recommendations=theme_recommendations,
    )


def run_propose_project_requests(
    pipeline_input: ProposeProjectRequestsInput,
) -> ProposeProjectRequestsOutput:
    opportunity_input = CreateOpportunitiesInput(
        config=pipeline_input.config,
        sales_plans=pipeline_input.sales_plans,
        accounts=pipeline_input.accounts,
        roles=pipeline_input.roles,
        titles=pipeline_input.titles,
        fiscal_periods=pipeline_input.fiscal_periods,
        staffs=pipeline_input.staffs,
        past_cases=pipeline_input.past_cases,
        past_case_roles=pipeline_input.past_case_roles,
        past_case_links=pipeline_input.past_case_links,
        request_human_approval=True,
    )
    output = run_scale_request_draft(
        opportunity_input,
        pipeline_input.theme_recommendations,
    )
    retrieved_evidence_chunks = build_project_request_retrieval_chunks(
        account_recommendations=output.account_recommendations,
        project_sizing_recommendations=output.project_sizing_recommendations,
        request_recommendations=output.request_recommendations,
        past_cases=pipeline_input.past_cases,
        past_case_roles=pipeline_input.past_case_roles,
    )
    proposal = run_table_proposal(
        spec=PipelineTaskSpec(
            task_name="propose_project_requests",
            prompt_version="propose_project_requests.v2",
            instructions=(
                "Use Knowledge/file_search to retrieve past cases relevant to the "
                "approved themes, then complete the account targeting, project sizing, "
                "and role request structure from those retrieved cases. The main "
                "responsibility is evidence discovery and evidence-grounded completion, "
                "not free-form project ideation. You may use multiple past cases to "
                "ground one account/project/request row when the rationale is clear. "
                "Return `account_recommendations`, `project_sizing_recommendations`, "
                "`request_recommendations`, and the actual "
                "`retrieved_evidence_chunks` that came from file_search. Do not return "
                "graph tables. For request rows, focus on which roles are supported by "
                "the evidence; deterministic repair will rebuild headcount, phase, "
                "allocation, request periods, and training slot policy from the chosen "
                "evidence cases. Return one row per supported role. Avoid unsupported "
                "request rows, and if evidence is weak, keep structure coverage and "
                "explain the gap in diagnostics. "
                "Each recommendation row must cite the retrieved case ids in "
                "`evidence_case_ids`."
            ),
            validators={
                "account_recommendations": AccountRecommendation.data_frame,
                "project_sizing_recommendations": ProjectSizingRecommendation.data_frame,
                "request_recommendations": RequestRecommendation.data_frame,
                "retrieved_evidence_chunks": RetrievedEvidenceChunk.data_frame,
            },
        ),
        input_tables={
            "sales_plans": pipeline_input.sales_plans,
            "accounts": pipeline_input.accounts,
            "roles": pipeline_input.roles,
            "titles": pipeline_input.titles if pipeline_input.titles is not None else pd.DataFrame(),
            "fiscal_periods": pipeline_input.fiscal_periods,
            "staffs": pipeline_input.staffs if pipeline_input.staffs is not None else pd.DataFrame(),
            "past_cases": pipeline_input.past_cases,
            "past_case_roles": pipeline_input.past_case_roles,
            "past_case_links": pipeline_input.past_case_links,
            "theme_recommendations": pipeline_input.theme_recommendations,
        },
        fallback_tables={
            "account_recommendations": output.account_recommendations,
            "project_sizing_recommendations": output.project_sizing_recommendations,
            "request_recommendations": output.request_recommendations,
            "retrieved_evidence_chunks": retrieved_evidence_chunks,
        },
        retrieved_evidence_chunks=retrieved_evidence_chunks,
    )
    online_mode = proposal.metadata().get("proposal_mode") == "online_llm"
    online_success = online_mode and not proposal.metadata().get("proposal_fallback_used")
    account_recommendations = proposal.tables["account_recommendations"]
    project_sizing_recommendations = proposal.tables["project_sizing_recommendations"]
    request_recommendations = proposal.tables["request_recommendations"]
    if online_success:
        (
            account_recommendations,
            project_sizing_recommendations,
            request_recommendations,
        ) = sync_project_request_evidence(
            account_recommendations=account_recommendations,
            project_sizing_recommendations=project_sizing_recommendations,
            request_recommendations=request_recommendations,
            retrieved_evidence_chunks=proposal.tables["retrieved_evidence_chunks"],
        )
    request_recommendations = rebuild_request_quantitative_fields_from_evidence(
        request_recommendations,
        project_sizing_recommendations,
        pipeline_input,
    )
    request_recommendations = sanitize_request_recommendations(request_recommendations)
    project_review_issues = build_project_review_issues(
        project_sizing_recommendations,
        request_recommendations,
    )
    retrieved_evidence_chunks = (
        proposal.tables["retrieved_evidence_chunks"]
        if online_success
        else build_project_request_retrieval_chunks(
            account_recommendations=account_recommendations,
            project_sizing_recommendations=project_sizing_recommendations,
            request_recommendations=request_recommendations,
            past_cases=pipeline_input.past_cases,
            past_case_roles=pipeline_input.past_case_roles,
        )
    )
    rag_knowledge_nodes, rag_knowledge_edges = build_rag_knowledge_graph(
        accounts=pipeline_input.accounts,
        past_cases=pipeline_input.past_cases,
        past_case_roles=pipeline_input.past_case_roles,
        past_case_links=pipeline_input.past_case_links,
        retrieved_evidence_chunks=retrieved_evidence_chunks,
    )
    consistency_metrics = build_consistency_metrics(
        pipeline_input.sales_plans,
        pipeline_input.theme_recommendations,
        project_sizing_recommendations=project_sizing_recommendations,
        request_recommendations=request_recommendations,
        project_review_issues=project_review_issues,
    )
    return ProposeProjectRequestsOutput(
        knowledge_nodes=rag_knowledge_nodes,
        knowledge_edges=rag_knowledge_edges,
        account_recommendations=account_recommendations,
        project_sizing_recommendations=project_sizing_recommendations,
        request_recommendations=request_recommendations,
        consistency_metrics=consistency_metrics,
        project_review_issues=project_review_issues,
        retrieved_evidence_chunks=retrieved_evidence_chunks,
        proposal_runs=proposal.proposal_runs_frame(),
        proposal_diagnostics=proposal.proposal_diagnostics_frame(),
        proposal_metadata=proposal.metadata(),
    )


class ProposeProjectRequestsPipeline(
    StatelessPipeline[ProposeProjectRequestsInput, ProposeProjectRequestsOutput]
):
    name = "propose_project_requests"

    def run(
        self,
        pipeline_input: ProposeProjectRequestsInput,
    ) -> ProposeProjectRequestsOutput:
        return run_propose_project_requests(pipeline_input)

    def input_from_payload(
        self,
        payload: PipelinePayload,
        paths: PipelinePaths | None = None,
    ) -> ProposeProjectRequestsInput:
        require_approved_tables(payload, ["theme_recommendations"])
        opportunity_input = create_opportunities_input_from_payload(
            payload,
            paths=paths,
            request_human_approval=True,
        )
        return input_from_opportunity_input(
            opportunity_input,
            payload.tables["theme_recommendations"],
        )

    def output_to_payload(
        self,
        output: ProposeProjectRequestsOutput,
        base: PipelinePayload,
    ) -> PipelinePayload:
        return PipelinePayload(
            tables=merged_output_tables(
                base.tables,
                direct_tables={
                    "project_knowledge_nodes": output.knowledge_nodes,
                    "project_knowledge_edges": output.knowledge_edges,
                    "account_recommendations": output.account_recommendations,
                    "project_sizing_recommendations": output.project_sizing_recommendations,
                    "request_recommendations": output.request_recommendations,
                    "consistency_metrics": output.consistency_metrics,
                    "project_review_issues": output.project_review_issues,
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
                    "project_knowledge_nodes": output.knowledge_nodes,
                    "project_knowledge_edges": output.knowledge_edges,
                    "account_recommendations": output.account_recommendations,
                    "consistency_metrics": output.consistency_metrics,
                    "project_review_issues": output.project_review_issues,
                    "retrieved_evidence_chunks": output.retrieved_evidence_chunks,
                    "proposal_runs": output.proposal_runs,
                    "proposal_diagnostics": output.proposal_diagnostics,
                },
                extra_metadata={
                    **(output.proposal_metadata or {}),
                    "stage": "project_request_proposed",
                },
            ),
            approvals=base.approvals,
        )


def run_propose_project_requests_from_payload(
    payload: PipelinePayload,
    paths: PipelinePaths | None = None,
) -> PipelinePayload:
    return ProposeProjectRequestsPipeline().run_from_payload(payload, paths)


def load_payload(paths: PipelinePaths | None = None) -> PipelinePayload:
    resolved_paths = paths or default_pipeline_paths()
    return approve_tables(
        PipelinePayload(
            tables={
                **read_tables(
                    resolved_paths.sample_data_dir,
                    [
                        "sales_plans",
                        "accounts",
                        "roles",
                        "titles",
                        "fiscal_periods",
                        "staffs",
                    ],
                ),
                "theme_recommendations": read_csv(
                    resolved_paths.planning_data_dir, "theme_recommendations"
                ),
            }
        ),
        ["theme_recommendations"],
        actor="csv",
        comment="Loaded from approved local CSV.",
    )


def main() -> None:
    paths = default_pipeline_paths()
    output = run_propose_project_requests_from_payload(load_payload(paths), paths=paths)
    knowledge_nodes = pd.DataFrame(audit_rows(output.metadata, "project_knowledge_nodes"))
    knowledge_edges = pd.DataFrame(audit_rows(output.metadata, "project_knowledge_edges"))
    account_recommendations = pd.DataFrame(
        audit_rows(output.metadata, "account_recommendations")
    )
    retrieved_evidence_chunks = pd.DataFrame(
        audit_rows(output.metadata, "retrieved_evidence_chunks")
    )
    write_tables(
        paths.planning_data_dir,
        {
            "project_knowledge_nodes": knowledge_nodes,
            "project_knowledge_edges": knowledge_edges,
            "account_recommendations": account_recommendations,
            "project_sizing_recommendations": output.tables[
                "project_sizing_recommendations"
            ],
            "request_recommendations": output.tables["request_recommendations"],
            "consistency_metrics": output.tables["consistency_metrics"],
            "project_review_issues": output.tables["project_review_issues"],
            "retrieved_evidence_chunks": retrieved_evidence_chunks,
        },
    )
    print("Project/Request proposal completed.")
    print(f"- account_recommendations: {len(account_recommendations)}")
    print(
        "- project_sizing_recommendations: "
        f"{len(output.tables['project_sizing_recommendations'])}"
    )
    print(f"- request_recommendations: {len(output.tables['request_recommendations'])}")
