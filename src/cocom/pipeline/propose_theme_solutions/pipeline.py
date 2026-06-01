from cocom.agent.common.table_completion import PipelineTaskSpec, run_table_proposal
import pandas as pd
from cocom.pipeline.common.base import StatelessPipeline
from cocom.pipeline.common.csv_io import read_tables, write_tables
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
    merged_output_tables,
)
from cocom.pipeline.common.paths import default_pipeline_paths
from cocom.pipeline.common.consistency import (
    build_consistency_metrics,
    enforce_theme_revenue_totals,
)
from cocom.pipeline.common.evidence_graph import build_rag_knowledge_graph
from cocom.pipeline.common.retrieval import (
    build_theme_solution_retrieval_chunks,
    sync_theme_recommendation_evidence,
)
from cocom.schema import (
    RetrievedEvidenceChunk,
    ThemeRecommendation,
)
from .io import (
    ProposeThemeSolutionsInput,
    ProposeThemeSolutionsOutput,
)
from .knowledge_graph import (
    build_knowledge_graph,
    build_theme_candidates,
)
from .theme_selection import (
    select_theme_recommendations,
)


def input_from_opportunity_input(
    pipeline_input: CreateOpportunitiesInput,
) -> ProposeThemeSolutionsInput:
    return ProposeThemeSolutionsInput(
        config=pipeline_input.config,
        sales_plans=pipeline_input.sales_plans,
        accounts=pipeline_input.accounts,
        roles=pipeline_input.roles,
        fiscal_periods=pipeline_input.fiscal_periods,
        past_cases=pipeline_input.past_cases,
        past_case_roles=pipeline_input.past_case_roles,
        past_case_links=pipeline_input.past_case_links,
    )


def run_propose_theme_solutions(
    pipeline_input: ProposeThemeSolutionsInput,
) -> ProposeThemeSolutionsOutput:
    sales_plans = pipeline_input.sales_plans.copy()
    sales_plans.attrs["annual_opportunity_count"] = int(
        pipeline_input.config.get("portfolio", {}).get(
            "annual_opportunity_count",
            20,
        )
    )
    fallback_knowledge_nodes, fallback_knowledge_edges = build_knowledge_graph(
        pipeline_input.accounts,
        pipeline_input.past_cases,
        pipeline_input.past_case_roles,
        pipeline_input.past_case_links,
    )
    theme_candidates = build_theme_candidates(
        sales_plans,
        pipeline_input.past_cases,
    )
    theme_recommendations = select_theme_recommendations(
        sales_plans=sales_plans,
        theme_candidates=theme_candidates,
    )
    retrieved_evidence_chunks = build_theme_solution_retrieval_chunks(
        theme_recommendations=theme_recommendations,
        past_cases=pipeline_input.past_cases,
    )
    proposal = run_table_proposal(
        spec=PipelineTaskSpec(
            task_name="propose_theme_solutions",
            prompt_version="propose_theme_solutions.v2",
            instructions=(
                "Use Knowledge/file_search to retrieve past cases relevant to each sales "
                "plan and complete the theme recommendation structure from those "
                "retrieved cases. The main responsibility is evidence discovery and "
                "evidence-grounded completion, not free-form ideation. You may ground "
                "one theme recommendation in multiple past cases when the rationale is "
                "clear. Return `theme_recommendations` plus the actual "
                "`retrieved_evidence_chunks` that came from file_search. Do not return "
                "graph tables. Do not invent unsupported themes. Each theme "
                "recommendation must cite the retrieved case ids in "
                "`evidence_case_ids`."
            ),
            validators={
                "theme_recommendations": ThemeRecommendation.data_frame,
                "retrieved_evidence_chunks": RetrievedEvidenceChunk.data_frame,
            },
        ),
        input_tables={
            "sales_plans": pipeline_input.sales_plans,
            "accounts": pipeline_input.accounts,
            "roles": pipeline_input.roles,
            "fiscal_periods": pipeline_input.fiscal_periods,
            "past_cases": pipeline_input.past_cases,
            "past_case_roles": pipeline_input.past_case_roles,
            "past_case_links": pipeline_input.past_case_links,
        },
        fallback_tables={
            "theme_recommendations": theme_recommendations,
            "retrieved_evidence_chunks": retrieved_evidence_chunks,
        },
        retrieved_evidence_chunks=retrieved_evidence_chunks,
    )
    online_mode = proposal.metadata().get("proposal_mode") == "online_llm"
    online_success = online_mode and not proposal.metadata().get("proposal_fallback_used")
    proposed_theme_recommendations = proposal.tables["theme_recommendations"]
    if online_success:
        proposed_theme_recommendations = sync_theme_recommendation_evidence(
            theme_recommendations=proposed_theme_recommendations,
            retrieved_evidence_chunks=proposal.tables["retrieved_evidence_chunks"],
        )
    repaired_theme_recommendations = enforce_theme_revenue_totals(
        pipeline_input.sales_plans,
        proposed_theme_recommendations,
    )
    retrieved_evidence_chunks = (
        proposal.tables["retrieved_evidence_chunks"]
        if online_success
        else build_theme_solution_retrieval_chunks(
            theme_recommendations=repaired_theme_recommendations,
            past_cases=pipeline_input.past_cases,
        )
    )
    rag_knowledge_nodes, rag_knowledge_edges = build_rag_knowledge_graph(
        accounts=pipeline_input.accounts,
        past_cases=pipeline_input.past_cases,
        past_case_roles=pipeline_input.past_case_roles,
        past_case_links=pipeline_input.past_case_links,
        retrieved_evidence_chunks=retrieved_evidence_chunks,
    )
    knowledge_nodes = (
        rag_knowledge_nodes if online_success and not rag_knowledge_nodes.empty else fallback_knowledge_nodes
    )
    knowledge_edges = (
        rag_knowledge_edges if online_success and not rag_knowledge_edges.empty else fallback_knowledge_edges
    )
    consistency_metrics = build_consistency_metrics(
        pipeline_input.sales_plans,
        repaired_theme_recommendations,
    )
    return ProposeThemeSolutionsOutput(
        knowledge_nodes=knowledge_nodes,
        knowledge_edges=knowledge_edges,
        theme_candidates=theme_candidates,
        theme_recommendations=repaired_theme_recommendations,
        consistency_metrics=consistency_metrics,
        retrieved_evidence_chunks=retrieved_evidence_chunks,
        proposal_runs=proposal.proposal_runs_frame(),
        proposal_diagnostics=proposal.proposal_diagnostics_frame(),
        proposal_metadata=proposal.metadata(),
    )


class ProposeThemeSolutionsPipeline(
    StatelessPipeline[ProposeThemeSolutionsInput, ProposeThemeSolutionsOutput]
):
    name = "propose_theme_solutions"

    def run(
        self,
        pipeline_input: ProposeThemeSolutionsInput,
    ) -> ProposeThemeSolutionsOutput:
        return run_propose_theme_solutions(pipeline_input)

    def input_from_payload(
        self,
        payload: PipelinePayload,
        paths: PipelinePaths | None = None,
    ) -> ProposeThemeSolutionsInput:
        opportunity_input = create_opportunities_input_from_payload(
            payload,
            paths=paths,
            request_human_approval=True,
        )
        return input_from_opportunity_input(opportunity_input)

    def output_to_payload(
        self,
        output: ProposeThemeSolutionsOutput,
        base: PipelinePayload,
    ) -> PipelinePayload:
        return PipelinePayload(
            tables=merged_output_tables(
                base.tables,
                direct_tables={
                    "knowledge_nodes": output.knowledge_nodes,
                    "knowledge_edges": output.knowledge_edges,
                    "theme_candidates": output.theme_candidates,
                    "theme_recommendations": output.theme_recommendations,
                    "consistency_metrics": output.consistency_metrics,
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
                    "knowledge_nodes": output.knowledge_nodes,
                    "knowledge_edges": output.knowledge_edges,
                    "theme_candidates": output.theme_candidates,
                    "consistency_metrics": output.consistency_metrics,
                    "retrieved_evidence_chunks": output.retrieved_evidence_chunks,
                    "proposal_runs": output.proposal_runs,
                    "proposal_diagnostics": output.proposal_diagnostics,
                },
                extra_metadata={
                    **(output.proposal_metadata or {}),
                    "stage": "theme_solution_proposed",
                },
            ),
            approvals=base.approvals,
        )


def run_propose_theme_solutions_from_payload(
    payload: PipelinePayload,
    paths: PipelinePaths | None = None,
) -> PipelinePayload:
    return ProposeThemeSolutionsPipeline().run_from_payload(payload, paths)


def load_payload(paths: PipelinePaths | None = None) -> PipelinePayload:
    resolved_paths = paths or default_pipeline_paths()
    return PipelinePayload(
        tables=read_tables(
            resolved_paths.sample_data_dir,
            ["sales_plans", "accounts", "roles", "fiscal_periods"],
        )
    )


def main() -> None:
    paths = default_pipeline_paths()
    output = run_propose_theme_solutions_from_payload(load_payload(paths), paths=paths)
    knowledge_nodes = pd.DataFrame(audit_rows(output.metadata, "knowledge_nodes"))
    knowledge_edges = pd.DataFrame(audit_rows(output.metadata, "knowledge_edges"))
    theme_candidates = pd.DataFrame(audit_rows(output.metadata, "theme_candidates"))
    retrieved_evidence_chunks = pd.DataFrame(
        audit_rows(output.metadata, "retrieved_evidence_chunks")
    )
    write_tables(
        paths.planning_data_dir,
        {
            "knowledge_nodes": knowledge_nodes,
            "knowledge_edges": knowledge_edges,
            "theme_candidates": theme_candidates,
            "theme_recommendations": output.tables["theme_recommendations"],
            "consistency_metrics": output.tables["consistency_metrics"],
            "retrieved_evidence_chunks": retrieved_evidence_chunks,
        },
    )
    print("Theme/Solution proposal completed.")
    print(f"- theme_recommendations: {len(output.tables['theme_recommendations'])}")
