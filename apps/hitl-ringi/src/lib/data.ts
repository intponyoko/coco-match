import { useEffect, useState } from "react";

export type Row = Record<string, string | number | boolean | null | undefined>;

export type AppData = {
  sample: Record<string, Row[]>;
  planning: Record<string, Row[]>;
  derived: Record<string, unknown>;
  generatedAt: string;
};

const SESSION_TABLES_KEY = "coco-match-session-tables-v1";
const SESSION_TABLES_EVENT = "coco-match-session-tables-updated";
const SESSION_SAMPLE_TABLES = new Set(["sales_plans"]);
const SESSION_PLANNING_TABLES = new Set([
  "theme_recommendations",
  "project_sizing_recommendations",
  "request_recommendations",
  "opportunities",
  "opportunity_requests",
  "staff_preference_options",
  "staff_preference_submissions",
  "assignment_recommendations",
  "opportunity_assignments",
  "matching_trace",
  "staff_utilization",
  "knowledge_nodes",
  "knowledge_edges",
  "project_knowledge_nodes",
  "project_knowledge_edges",
  "opportunity_recommendations",
  "retrieved_evidence_chunks",
  "proposal_runs",
  "proposal_diagnostics",
  "consistency_metrics",
  "project_review_issues",
]);
const OPTIONAL_SESSION_TABLES = [
  "request_recommendations",
  "opportunity_recommendations",
  "knowledge_edges",
  "knowledge_nodes",
  "project_knowledge_edges",
  "project_knowledge_nodes",
  "retrieved_evidence_chunks",
  "matching_trace",
  "staff_utilization",
  "proposal_runs",
  "proposal_diagnostics",
  "consistency_metrics",
  "project_review_issues",
];

type DataState = {
  data: AppData | null;
  loading: boolean;
  error: string | null;
};

export function useAppData(): DataState {
  const [state, setState] = useState<DataState>({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    let baseData: AppData | null = null;
    const controller = new AbortController();

    function updateFromSession() {
      if (!baseData || cancelled) {
        return;
      }
      setState({ data: mergeSessionTables(baseData), loading: false, error: null });
    }

    function handleStorage(event: StorageEvent) {
      if (event.key === SESSION_TABLES_KEY) {
        updateFromSession();
      }
    }

    const timeout = window.setTimeout(() => {
      controller.abort();
    }, 10000);

    fetch("/data/app-data.json", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error(
              "Missing /data/app-data.json. Run `bun run export:data` or restart `bun run dev` after data bootstrap.",
            );
          }
          throw new Error(`Failed to load app-data.json: ${response.status}`);
        }
        return response.json() as Promise<AppData>;
      })
      .then((data) => {
        if (!cancelled) {
          window.clearTimeout(timeout);
          baseData = data;
          setState({ data: mergeSessionTables(data), loading: false, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          window.clearTimeout(timeout);
          setState({
            data: null,
            loading: false,
            error: error instanceof Error ? error.message : String(error),
          });
        }
      });
    window.addEventListener(SESSION_TABLES_EVENT, updateFromSession);
    window.addEventListener("storage", handleStorage);

    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timeout);
      window.removeEventListener(SESSION_TABLES_EVENT, updateFromSession);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  return state;
}

export function readSessionTables(): Record<string, Row[]> {
  if (typeof window === "undefined") {
    return {};
  }
  const raw = window.localStorage.getItem(SESSION_TABLES_KEY);
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw) as Record<string, Row[]>;
  } catch {
    return {};
  }
}

export function writeSessionTables(tables: Record<string, Row[]>): void {
  if (typeof window === "undefined") {
    return;
  }
  const compactTables = compactSessionTables(tables);
  try {
    window.localStorage.setItem(SESSION_TABLES_KEY, JSON.stringify(compactTables));
  } catch (error) {
    const reducedTables = omitTables(compactTables, OPTIONAL_SESSION_TABLES);
    window.localStorage.setItem(SESSION_TABLES_KEY, JSON.stringify(reducedTables));
    if (error instanceof Error) {
      console.warn(`Reduced session tables after localStorage write failed: ${error.message}`);
    }
  }
  window.dispatchEvent(new Event(SESSION_TABLES_EVENT));
}

export function clearSessionTables(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(SESSION_TABLES_KEY);
  window.dispatchEvent(new Event(SESSION_TABLES_EVENT));
}

export function mergeSessionTables(data: AppData): AppData {
  const sessionTables = readSessionTables();
  return {
    ...data,
    sample: mergeKnownTables(data.sample, sessionTables),
    planning: mergePlanningTables(data.sample, data.planning, sessionTables),
  };
}

function mergeKnownTables(
  base: Record<string, Row[]>,
  sessionTables: Record<string, Row[]>,
) {
  const merged = { ...base };
  for (const [name, table] of Object.entries(sessionTables)) {
    if (name in base) {
      merged[name] = table;
    }
  }
  return merged;
}

function mergePlanningTables(
  sample: Record<string, Row[]>,
  planning: Record<string, Row[]>,
  sessionTables: Record<string, Row[]>,
) {
  const merged = { ...planning };
  for (const [name, table] of Object.entries(sessionTables)) {
    if (!(name in sample)) {
      merged[name] = table;
    }
  }
  return merged;
}

function compactSessionTables(tables: Record<string, Row[]>): Record<string, Row[]> {
  const compact: Record<string, Row[]> = {};
  for (const [name, table] of Object.entries(tables)) {
    if (!Array.isArray(table)) {
      continue;
    }
    if (SESSION_SAMPLE_TABLES.has(name) || SESSION_PLANNING_TABLES.has(name)) {
      compact[name] = table;
    }
  }
  return compact;
}

function omitTables(
  tables: Record<string, Row[]>,
  tableNames: string[],
): Record<string, Row[]> {
  const omitted = new Set(tableNames);
  return Object.fromEntries(
    Object.entries(tables).filter(([name]) => !omitted.has(name)),
  );
}

export function rows(data: AppData | null, source: "sample" | "planning", name: string): Row[] {
  return data?.[source]?.[name] ?? [];
}

export function numberValue(value: unknown): number {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }
  if (typeof value === "string") {
    const parsed = Number(value.replaceAll(",", ""));
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

export function sumBy(items: Row[], key: string): number {
  return items.reduce((total, item) => total + numberValue(item[key]), 0);
}

export function byCode(items: Row[], codeKey = "code"): Map<string, Row> {
  return new Map(items.map((item) => [String(item[codeKey] ?? ""), item]));
}
