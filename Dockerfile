FROM python:3.14-slim AS app-data

WORKDIR /work
COPY data ./data
COPY apps/hitl-ringi/scripts ./apps/hitl-ringi/scripts
RUN python apps/hitl-ringi/scripts/export_artifacts.py


FROM oven/bun:1.3.13 AS web-build

WORKDIR /work/apps/hitl-ringi
COPY apps/hitl-ringi/package.json apps/hitl-ringi/bun.lock ./
RUN bun install --frozen-lockfile
COPY apps/hitl-ringi ./
COPY --from=app-data /work/apps/hitl-ringi/public/data/app-data.json ./public/data/app-data.json
ENV PUBLIC_COCO_MATCH_API_BASE_URL=
ENV PUBLIC_COCO_MATCH_API_PREFIX=/api/v1
RUN bun run build:static


FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV COCO_MATCH_STATIC_DIR=/app/static

COPY src ./src
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY configs ./configs
COPY knowledge ./knowledge
COPY data ./data
COPY --from=web-build /work/apps/hitl-ringi/dist ./static

EXPOSE 8000
CMD [".venv/bin/uvicorn", "cocom.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
