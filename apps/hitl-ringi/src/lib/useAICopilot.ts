import { useCallback, useEffect, useState } from "react";
import { runInsightEndpoint, type AgentInsightResponse, type AgentInsightStage, type PipelineTables } from "./apiClient";

type InsightPayload = {
  tables: PipelineTables;
  approvals?: Record<string, Record<string, unknown>>;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  stage: AgentInsightStage | string;
  focus?: Record<string, unknown>;
};

type UseAICopilotOptions = {
  enabled?: boolean;
  payload: InsightPayload | null;
};

export function useAICopilot({ enabled = true, payload }: UseAICopilotOptions) {
  const [response, setResponse] = useState<AgentInsightResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState(true);
  const payloadKey = payloadSignature(payload);

  const request = useCallback(async () => {
    if (!enabled || !payload) {
      return;
    }
    if (!available) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await runInsightEndpoint(payload);
      setResponse(next);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (isUnavailableError(message)) {
        setAvailable(false);
        setError(null);
        return;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [available, enabled, payload]);

  useEffect(() => {
    setResponse(null);
    setError(null);
  }, [payloadKey]);

  const refresh = useCallback(() => {
    if (!payload) {
      return;
    }
    void request();
  }, [payload, request]);

  return {
    response,
    loading,
    error,
    available,
    refresh,
  };
}

function isUnavailableError(message: string): boolean {
  return (
    message.includes("404")
    || message.includes("Failed to fetch")
    || message.includes("NetworkError")
  );
}

function payloadSignature(payload: InsightPayload | null): string {
  if (!payload) {
    return "";
  }
  return stableStringify({
    stage: payload.stage,
    focus: payload.focus ?? {},
    approvals: payload.approvals ?? {},
    tables: payload.tables,
  });
}

function stableStringify(value: unknown): string {
  return JSON.stringify(normalizeForSignature(value));
}

function normalizeForSignature(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(normalizeForSignature);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, normalizeForSignature(item)]),
    );
  }
  return value;
}
