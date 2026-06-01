import type { Row } from "./data";

export type PipelineTables = Record<string, Row[]>;

export type PipelinePayload = {
  tables: PipelineTables;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  approvals?: Record<string, Record<string, unknown>>;
};

export type AgentEvidence = {
  evidence_id: string;
  title: string;
  summary: string;
  source?: string;
  metadata?: Record<string, unknown>;
};

export type AgentResponse = PipelinePayload & {
  explanations?: Row[];
  evidence_refs?: AgentEvidence[];
  diagnostics?: Row[];
};

export type AgentInsightStage =
  | "sales_plan"
  | "theme_solution"
  | "project_request"
  | "project_interest"
  | "matching";

export type AgentInsightItem = {
  title?: string;
  body?: string;
  label?: string;
  value?: string | number;
  severity?: string;
  tag?: string;
  intent?: string;
};

export type AgentInsightResponse = {
  stage: AgentInsightStage | string;
  headline: string;
  summary: string;
  confidence_label?: string;
  confidence_score?: number;
  rationale?: AgentInsightItem[];
  watchouts?: AgentInsightItem[];
  alternatives?: AgentInsightItem[];
  suggested_actions?: AgentInsightItem[];
  impact?: AgentInsightItem[];
  evidence_refs?: AgentEvidence[];
  metadata?: Record<string, unknown>;
};

const API_BASE_URL =
  import.meta.env.PUBLIC_COCO_MATCH_API_BASE_URL ??
  import.meta.env.PUBLIC_COCOM_API_BASE_URL ??
  "http://127.0.0.1:8000";
const DEFAULT_API_PREFIX = import.meta.env.PUBLIC_COCO_MATCH_API_PREFIX ?? "/api/v1";

export async function runPipelineEndpoint(
  endpoint: string,
  payload: PipelinePayload,
): Promise<PipelinePayload> {
  const response = await fetch(apiUrl(endpoint), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      tables: payload.tables,
      config: payload.config ?? {},
      metadata: payload.metadata ?? {},
      approvals: payload.approvals ?? {},
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${endpoint} failed: ${response.status} ${detail}`);
  }
  return response.json() as Promise<PipelinePayload>;
}

export async function runAgentEndpoint(
  endpoint: string,
  payload: PipelinePayload,
): Promise<AgentResponse> {
  const response = await fetch(apiUrl(endpoint), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      tables: payload.tables,
      config: payload.config ?? {},
      metadata: payload.metadata ?? {},
      approvals: payload.approvals ?? {},
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${endpoint} failed: ${response.status} ${detail}`);
  }
  return response.json() as Promise<AgentResponse>;
}

export async function runInsightEndpoint(payload: {
  tables: PipelineTables;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  approvals?: Record<string, Record<string, unknown>>;
  stage: AgentInsightStage | string;
  focus?: Record<string, unknown>;
}): Promise<AgentInsightResponse> {
  const response = await fetch(apiUrl("/agent/insights"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      tables: payload.tables,
      config: payload.config ?? {},
      metadata: payload.metadata ?? {},
      approvals: payload.approvals ?? {},
      stage: payload.stage,
      focus: payload.focus ?? {},
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`/agent/insights failed: ${response.status} ${detail}`);
  }
  return response.json() as Promise<AgentInsightResponse>;
}

export async function loadEvidence(evidenceId: string): Promise<AgentEvidence> {
  const response = await fetch(apiUrl(`/agent/evidence/${encodeURIComponent(evidenceId)}`));
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`evidence failed: ${response.status} ${detail}`);
  }
  return response.json() as Promise<AgentEvidence>;
}

export async function loadWorkflow() {
  const response = await fetch(apiUrl("/pipeline/workflow"));
  if (!response.ok) {
    throw new Error(`workflow failed: ${response.status}`);
  }
  return response.json() as Promise<{ workflow: Row[] }>;
}

function apiUrl(endpoint: string): string {
  const base = API_BASE_URL.replace(/\/$/, "");
  const prefix = DEFAULT_API_PREFIX.replace(/\/$/, "");
  return `${base}${prefix}${endpoint}`;
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
