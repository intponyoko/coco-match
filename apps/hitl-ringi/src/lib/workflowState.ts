import type { ApprovalRecord, ApprovalStatus } from "./approvalState";
import type { AppData, Row } from "./data";

export type WorkflowRole = "経営層" | "部署層" | "個人層";

export type WorkflowNode = {
  step: number;
  role: WorkflowRole;
  title: string;
  ownerDescription: string;
  pagePath: string;
  tableNames: string[];
  completionStatuses: ApprovalStatus[];
  status: ApprovalStatus;
  isComplete: boolean;
  count: number;
};

const workflowDefinition: Omit<WorkflowNode, "status" | "isComplete" | "count">[] = [
  {
    step: 1,
    role: "経営層",
    title: "SalesPlan作成・承認",
    ownerDescription: "経営層が年間売上計画を確定します。",
    pagePath: "/sales-plan",
    tableNames: ["sales_plans"],
    completionStatuses: ["approved"],
  },
  {
    step: 2,
    role: "部署層",
    title: "Theme / Solution承認",
    ownerDescription: "部署層が営業計画から狙うThemeとSolutionを決めます。",
    pagePath: "/theme-solutions",
    tableNames: ["theme_recommendations"],
    completionStatuses: ["approved"],
  },
  {
    step: 3,
    role: "部署層",
    title: "PJ規模 / Requests承認",
    ownerDescription: "部署層がAccount、PJ規模、Role別Requestを調整します。",
    pagePath: "/project-requests",
    tableNames: ["project_sizing_recommendations", "request_recommendations"],
    completionStatuses: ["approved"],
  },
  {
    step: 4,
    role: "個人層",
    title: "年間PJ希望・研修希望",
    ownerDescription: "個人がPJ参画希望と研修希望を提出します。",
    pagePath: "/project-interest",
    tableNames: ["staff_preference_submissions"],
    completionStatuses: ["submitted", "approved"],
  },
  {
    step: 5,
    role: "部署層",
    title: "Matching実施・承認",
    ownerDescription: "部署層がMatching案を確認し、最終アサインを確定します。",
    pagePath: "/matching",
    tableNames: ["assignment_recommendations"],
    completionStatuses: ["approved"],
  },
];

export function workflowDefinitions() {
  return workflowDefinition;
}

export function workflowNodesFromAppData(
  data: AppData | null,
  records: ApprovalRecord[],
): WorkflowNode[] {
  return workflowNodesFromTables(
    {
      ...(data?.sample ?? {}),
      ...(data?.planning ?? {}),
    },
    records,
  );
}

export function workflowNodesFromTables(
  tables: Record<string, Row[]>,
  records: ApprovalRecord[],
): WorkflowNode[] {
  const latest = latestRecordByTable(records);
  return workflowDefinition.map((definition) => {
    const statuses = definition.tableNames.map((tableName) =>
      latest.get(tableName)?.status ?? fallbackStatus(tableName, tables),
    );
    const isComplete = statuses.every((status) =>
      definition.completionStatuses.includes(status),
    );
    return {
      ...definition,
      status: aggregateStatus(statuses),
      isComplete,
      count: definition.tableNames.reduce(
        (total, tableName) => total + (tables[tableName]?.length ?? 0),
        0,
      ),
    };
  });
}

export function workflowStepperRows(nodes: WorkflowNode[]) {
  return nodes.map((node) => ({
    label: `${node.step}. ${node.title}`,
    status: node.status,
    count: node.count,
  }));
}

function latestRecordByTable(records: ApprovalRecord[]) {
  const latest = new Map<string, ApprovalRecord>();
  for (const record of records) {
    latest.set(record.tableName, record);
  }
  return latest;
}

function fallbackStatus(
  tableName: string,
  tables: Record<string, Row[]>,
): ApprovalStatus {
  if (tableName === "sales_plans") {
    return tables.sales_plans?.length ? "draft" : "pending";
  }
  return tables[tableName]?.length ? "draft" : "pending";
}

function aggregateStatus(statuses: ApprovalStatus[]): ApprovalStatus {
  if (statuses.every((status) => status === "approved")) {
    return "approved";
  }
  if (statuses.includes("edited")) {
    return "edited";
  }
  if (statuses.includes("submitted")) {
    return "submitted";
  }
  if (statuses.includes("draft")) {
    return "draft";
  }
  return "pending";
}
