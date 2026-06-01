# COCOM

COCOM is a small planning sandbox for generating sample organization data,
creating opportunity/request drafts from SalesPlan and past-case knowledge, and
matching approved requests to staff capacity.

## Planning Commands

```bash
uv run propose-theme-solutions
uv run propose-project-requests
uv run materialize-opportunities
uv run propose-assignment-options
uv run propose-assignments
uv run finalize-assignments
uv run run-all
uv run serve-api
```

Generate demo input CSVs separately when needed:

```bash
uv run generate-sample
```

HITL review is exposed through the stateless FastAPI endpoints under
`/api/v1/pipeline/*`. Existing unversioned `/pipeline/*` endpoints are kept for
compatibility. The local CSV commands are adapters around the same subpipelines;
later stages consume table-level approvals carried in the API payload. Local CSV
commands treat their loaded review tables as already approved.

AI-assisted HITL endpoints are exposed under `/api/v1/agent/*` with unversioned
aliases under `/agent/*`. They run with a deterministic local fallback by
default. Set the Foundry variables to use Azure AI Foundry Agent Service.

```bash
AZURE_FOUNDRY_PROJECT_ENDPOINT=https://<foundry-resource>.services.ai.azure.com/api/projects/<project-name>
AZURE_FOUNDRY_AGENT_ID=<agent-id>
AZURE_FOUNDRY_API_VERSION=v1
AZURE_FOUNDRY_BEARER_TOKEN=<local-test-token>
```

The Astro app calls `/api/v1` by default. Override with
`PUBLIC_COCO_MATCH_API_PREFIX=""` if you need to call the legacy unversioned
routes.

## Docker SSG Deployment

The repository includes a multi-stage `Dockerfile` that builds the Astro SSG app
and serves it from the FastAPI container. The browser and API share one origin,
so CORS is not involved.

```bash
docker build -t coco-match:ssg .
docker run --rm -p 8000:8000 coco-match:ssg
```

The container serves:

- `/` and page routes such as `/sales-plan/` from Astro static files
- `/api/v1/*` from FastAPI
- legacy `/pipeline/*` and `/agent/*` routes for compatibility

For cross-origin deployments, set `COCO_MATCH_CORS_ORIGINS` to a comma-separated
allowlist such as `https://coco-match.example.com`. The default remains `*` for
local development and same-origin SSG deployment does not require CORS.

Open the Streamlit review app with:

```bash
uv run streamlit run app.py
```

## Structure

- `src/cocom/schema`: Pandera schemas for master and fact tables.
- `src/cocom/pipeline`: Stateless subpipelines. Each subpipeline owns its
  pipeline entrypoint and its local business logic.
- `src/cocom/api`: Stateless FastAPI adapter for the pipeline.
- `configs`: TOML settings for sample-data generation and opportunity creation.
- `knowledge`: Past-case knowledge used to derive themes, project scale, roles,
  and training/OJT policy.
- `pages`: Streamlit multipage review and validation UI.
