# RAG Grounding Implementation

## Purpose

The planning pipeline now treats retrieval as a first-class intermediate artifact instead of an implicit side effect hidden inside deterministic scoring code.

The goal is to keep the public pipeline I/O stable while making both offline and online execution expose the same retrieval-shaped grounding surface.

## New Table

`retrieved_evidence_chunks` is appended by each proposal-stage pipeline.

Columns:

- `task_name`
- `target_table`
- `target_code`
- `evidence_id`
- `evidence_type`
- `title`
- `snippet`
- `score`
- `source`
- `retrieval_rank`

This table is the shared contract between:

- offline deterministic retrieval
- online Foundry-backed retrieval
- LLM proposal generation
- UI evidence and audit surfaces

## Current Retrieval Strategy

### `propose_theme_solutions`

- Uses `theme_recommendations.evidence_case_ids`
- Expands each case ID into case-level snippets from `past_cases`

### `propose_project_requests`

- Uses `project_sizing_recommendations.evidence_case_ids`
- Expands both:
  - case-level snippets from `past_cases`
  - role-level snippets from `past_case_roles`

### `propose_assignment_options`

- Uses generated `staff_preference_options`
- Emits execution evidence based on assignment type, skill gap, allocation, and option reason

### `propose_assignments`

- Uses `matching_trace`, optional `staff_preference_options`, and `staff_utilization`
- Emits evidence describing why a specific recommendation was selected or risky

## Proposal Engine Contract

Proposal tasks still return normalized output tables, but the prompt input now includes retrieval artifacts in addition to generic table summaries.

The intended online/offline contract is:

1. Build deterministic fallback output tables
2. Build `retrieved_evidence_chunks`
3. Pass both summaries and retrieved chunks to the proposal engine
4. Normalize LLM output back to typed tables

This lets Foundry-backed retrieval replace only the internals of step 2 without changing downstream pipeline consumers.

## Online vs Offline Separation

The execution rule is strict:

- If the LLM path succeeds, the returned tables must come only from the LLM response.
- If the LLM path fails or returns incomplete structured data, the pipeline falls back to deterministic output for the whole task.
- The system must not mix deterministic fallback rows into a partially successful online response.

This rule is enforced in the common proposal runner so every LLM-enabled proposal pipeline follows the same boundary.

## Foundry Migration Path

The next online step is to replace deterministic retrieval chunk construction with Foundry `file_search` results normalized into the same `retrieved_evidence_chunks` table.

Recommended sequence:

1. Create a vector store for past case documents
2. Attach `file_search` to the hosted agent
3. Retrieve top-k chunks per target row
4. Normalize chunk metadata into `retrieved_evidence_chunks`
5. Keep proposal output schemas unchanged
