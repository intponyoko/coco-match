import { runAgentEndpoint, runPipelineEndpoint, type AgentResponse, type PipelineTables } from "./apiClient";
import { readSessionTables, writeSessionTables, type AppData, type Row } from "./data";

export type ApprovalMap = Record<string, Record<string, unknown>>;

export function tablesFromAppData(data: AppData | null): PipelineTables {
  return {
    ...(data?.sample ?? {}),
    ...(data?.planning ?? {}),
    ...readSessionTables(),
  };
}

export function approveTable(
  approvals: ApprovalMap,
  tableName: string,
  actor: string,
  comment = "",
): ApprovalMap {
  return {
    ...approvals,
    [tableName]: {
      status: "approved",
      actor,
      comment,
      approved_at: new Date().toISOString(),
    },
  };
}

export async function runWorkflowEndpoint(
  endpoint: string,
  tables: PipelineTables,
  approvals: ApprovalMap,
) {
  const response = await runPipelineEndpoint(endpoint, { tables, approvals });
  writeSessionTables(sessionTablesFromPayload(response));
  return response;
}

export async function runAgentWorkflowEndpoint(
  endpoint: string,
  tables: PipelineTables,
  approvals: ApprovalMap,
): Promise<AgentResponse> {
  const response = await runAgentEndpoint(endpoint, { tables, approvals });
  writeSessionTables(sessionTablesFromPayload(response));
  return response;
}

function sessionTablesFromPayload(payload: {
  tables: PipelineTables;
  metadata?: Record<string, unknown>;
}): Record<string, Row[]> {
  return {
    ...auditArtifactTables(payload.metadata),
    ...(payload.tables as Record<string, Row[]>),
  };
}

function auditArtifactTables(
  metadata: Record<string, unknown> | undefined,
): Record<string, Row[]> {
  const auditArtifacts = metadata?.audit_artifacts;
  if (!auditArtifacts || typeof auditArtifacts !== "object") {
    return {};
  }
  const rows: Record<string, Row[]> = {};
  for (const [name, value] of Object.entries(auditArtifacts)) {
    if (Array.isArray(value)) {
      rows[name] = value as Row[];
    }
  }
  return rows;
}
