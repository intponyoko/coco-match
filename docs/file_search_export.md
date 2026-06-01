# File Search Export

## Purpose

`data/file_search/` is a generated staging directory for Azure Foundry `file_search`.

The source of truth remains:

- `knowledge/past_cases/past_cases.csv`
- `knowledge/past_cases/past_case_roles.csv`
- `knowledge/past_cases/past_case_links.csv`

The export contract is:

- `1 file = 1 past case`
- `1 vector store = many case documents`
- each document contains both case summary and role-demand evidence

## Output Format

The exporter writes:

- `data/file_search/case-<case_id>.md`
- `data/file_search/_manifest.json`

Each case document includes:

- case metadata
- themes
- customer pain
- role demand summary
- role phase details
- related cases

This shape is intentionally optimized for:

- `propose_theme_solutions`
- `propose_project_requests`

It is not intended to store pipeline-generated artifacts such as:

- `knowledge_nodes`
- `knowledge_edges`
- `theme_recommendations`
- `request_recommendations`

Those are derived tables, not retrieval source documents.

## Generation

Preferred command:

```bash
uv run export-file-search
```

Alternative:

```bash
.venv/bin/python -m cocom.pipeline.export_file_search
```

## Upload Expectation

The upload target is the set of `case-*.md` files inside `data/file_search/`.

Recommended Foundry flow:

1. Create or select one vector store for past-case knowledge.
2. Upload every `case-*.md` file.
3. Wait until ingestion status is `completed`.
4. Attach that vector store to the hosted agent's `file_search` tool.

`_manifest.json` is for local inspection and should not be relied on as retrieval content.
