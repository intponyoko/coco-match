# Planning Pipeline / HITL / State Machine

This document records the current stateless planning pipeline contract.

## Workflow

```text
SalesPlan and master tables are loaded
  -> Propose Theme/Solution
  -> HITL 1: department edits and approves the Theme/Solution table
  -> Propose Project Scale/Requests
  -> HITL 2: department edits and approves the ProjectSpec and Request tables
  -> Materialize Opportunities/Requests
  -> HITL 3: individuals submit the StaffPreference table
  -> Propose Assignments
  -> HITL 4: department edits and approves the AssignmentRecommendation table
  -> Finalize Assignments
```

## State Machine

| Stage | Owner | Next action |
|---|---|---|
| `theme_solution_proposed` | department | edit and approve `theme_recommendations` |
| `theme_solution_approved` | system | `propose_project_requests` |
| `project_request_proposed` | department | edit and approve `project_sizing_recommendations` and `request_recommendations` |
| `project_request_approved` | system | `materialize_opportunities` |
| `opportunities_materialized` | individual | submit project/training preferences |
| `staff_preferences_collected` | system | `propose_assignments` |
| `assignments_proposed` | department | edit and approve `assignment_recommendations` |
| `assignments_finalized` | system | complete |

## Stateless API Contract

All API endpoints are stateless.

- Requests use JSON records: `{"tables": {"table_name": [{...}]}, "config": {}, "metadata": {}, "approvals": {}}`.
- Responses use the same shape and return every table needed by the next subpipeline.
- The API does not persist approvals, audit logs, or generated tables.
- CSV read/write is a local CLI adapter concern only.
- HITL state is owned by the caller. In the current Astro prototype, browser state holds edited tables and table-level approvals.
- A downstream subpipeline only checks whether required input tables are approved; it does not inspect row-level approval columns.

## Subpipeline IO

| Subpipeline | Input tables | Output tables |
|---|---|---|
| `propose_theme_solutions` | `sales_plans`, `accounts`, `roles`, `fiscal_periods` | `knowledge_nodes`, `knowledge_edges`, `theme_candidates`, `theme_recommendations` |
| `propose_project_requests` | table-approved `theme_recommendations` plus sample tables | `account_recommendations`, `project_sizing_recommendations`, `request_recommendations` |
| `materialize_opportunities` | table-approved `project_sizing_recommendations`, table-approved `request_recommendations` | `opportunities`, `opportunity_requests`, `opportunity_recommendations`, `allocation_trace` |
| `propose_assignment_options` | `opportunities`, `opportunity_requests`, `staffs` | `staff_preference_options` |
| `propose_assignments` | `opportunity_requests`, `role_skills`, `staff_career`, `staffs`, `fiscal_periods` | `assignment_recommendations`, `matching_trace`, `staff_utilization` |
| `finalize_assignments` | table-approved `assignment_recommendations` | `opportunity_assignments` |

## API Endpoints

```text
GET  /health
GET  /pipeline/workflow
POST /pipeline/propose-theme-solutions
POST /pipeline/propose-project-requests
POST /pipeline/materialize-opportunities
POST /pipeline/propose-assignment-options
POST /pipeline/propose-assignments
POST /pipeline/finalize-assignments
POST /pipeline/run-all
```
