# Knowledge Data

This directory contains source knowledge data used to derive planning outputs
from master data and sales plans. TOML configuration lives under `configs/`.

## Files

- `past_cases/past_cases.csv`: source-of-truth historical cases with observed
  revenue, duration, theme, customer pain, outcome, and delivery model.
- `past_cases/past_case_roles.csv`: observed phase, role, headcount, allocation,
  and phase timing by historical case.
- `past_cases/past_case_links.csv`: observed expansion or follow-on
  relationships between historical cases.

Related config files:

- `configs/sample_data/generation.toml`: sample-data generation settings.
- `configs/opportunity_creation/core.toml`: metadata for the current generation
  source.
- `configs/opportunity_creation/workflow.toml`: human-in-the-loop
  recommendation workflow and recommendation output settings.

## Current Role

The current implementation treats `knowledge/past_cases/` as the source of
truth and transforms those CSV files into a compact deterministic graph. Past
cases carry observed facts:

- target industry and solution
- observed revenue and duration
- business theme and customer pain
- outcome and period hint
- observed phase, role, headcount, allocation, and phase timing

`uv run run-all` loads the workflow settings and past-case data through
the pipeline. Sales plans provide the revenue envelope; past-case graph views
provide the grounded themes, sizing evidence, and request evidence.

## Intended HITL Recommendation Workflow

The intended workflow for opportunity planning is:

1. Start from approved `sales_plans`.
2. Retrieve similar cases from this knowledge base by industry, solution,
   seasonality, project size, business theme, and historical role patterns.
3. Use an LLM/RAG step to propose opportunity candidates with evidence:
   referenced case IDs, estimated revenue, size band, duration, solution,
   rationale, and draft delivery shape.
4. Have a human planner review the recommendations. The planner can accept,
   reject, merge, split, retime, resize, or override any opportunity.
5. Commit only approved opportunities into the planning output.
6. Generate opportunity requests from the approved opportunities and the same
   referenced case evidence.
7. Feed results such as win/loss, staffing gaps, and actual delivery patterns
   back into the knowledge base.

For HITL operation, run the draft stages and approve or edit their CSV outputs:

1. `uv run create-theme-draft`
2. Review `data/planning/theme_recommendations.csv`.
3. `uv run create-scale-request-draft`
4. Review `data/planning/project_sizing_recommendations.csv` and
   `data/planning/request_recommendations.csv`.
5. `uv run materialize-approved`
6. `uv run match-assignment`

`uv run run-all` passes `request_human_approval=False` for demo execution, so it
deterministically writes `data/planning/opportunity_recommendations.csv`,
`opportunities.csv`, `opportunity_requests.csv`, matching outputs, and traces.

The LLM should not be the system of record. It recommends candidates and
explains evidence; the accepted opportunity set should always be attributable to
human approval and source cases.
