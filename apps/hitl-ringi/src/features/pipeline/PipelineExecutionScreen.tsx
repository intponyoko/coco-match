import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import HITLStageHeader from "../../components/HITLStageHeader";
import MetricCard from "../../components/MetricCard";
import SimpleBarChart from "../../components/SimpleBarChart";
import StatusBadge from "../../components/StatusBadge";
import WorkflowStepper from "../../components/WorkflowStepper";
import type { PipelineTables } from "../../lib/apiClient";
import { useApprovalState } from "../../lib/approvalState";
import { sumBy, useAppData, writeSessionTables, type Row } from "../../lib/data";
import { formatCurrency } from "../../lib/formatting";
import { groupCountRows, groupSumRows } from "../../lib/tableMetrics";
import { runWorkflowEndpoint } from "../../lib/workflowRunner";
import { workflowNodesFromTables, workflowStepperRows } from "../../lib/workflowState";

const DataFrameGrid = lazy(() => import("../../components/DataFrameGrid"));

type Stage =
  | "loaded"
  | "theme_solution_proposed"
  | "project_request_proposed"
  | "opportunities_materialized"
  | "staff_preference_options_proposed"
  | "assignments_proposed"
  | "assignments_finalized";

const endpoints = {
  theme: "/pipeline/propose-theme-solutions",
  project: "/pipeline/propose-project-requests",
  materialize: "/pipeline/materialize-opportunities",
  preferenceOptions: "/pipeline/propose-assignment-options",
  assignments: "/pipeline/propose-assignments",
  finalize: "/pipeline/finalize-assignments",
};

const reviewTables = [
  "sales_plans",
  "theme_recommendations",
  "project_sizing_recommendations",
  "request_recommendations",
  "staff_preference_options",
  "staff_preference_submissions",
  "assignment_recommendations",
];

const tableColumns: Record<string, string[]> = {
  sales_plans: ["code", "industry_code", "period_code", "target_revenue"],
  theme_recommendations: [
    "sales_plan_code",
    "industry_code",
    "theme_rank",
    "theme",
    "solution_code",
    "planned_revenue",
    "evidence_case_ids",
    "theme_score",
    "observed_revenue_mean",
    "observed_duration_mean",
    "delivery_model",
    "customer_pain",
  ],
  project_sizing_recommendations: [
    "sales_plan_code",
    "project_spec_code",
    "industry_code",
    "account_code",
    "account_name",
    "account_segment",
    "solution_code",
    "start_period_code",
    "estimated_revenue",
    "duration_months",
    "theme",
    "customer_pain",
    "evidence_case_ids",
    "grounding_score",
    "project_training_allowed",
    "project_training_max_skill_gap",
    "sizing_method",
    "delivery_model",
  ],
  request_recommendations: [
    "request_recommendation_code",
    "project_spec_code",
    "start_period_code",
    "end_period_code",
    "role_code",
    "allocation_percentage",
    "headcount",
    "training_slots",
    "project_training_max_skill_gap",
    "role_phase_training_max_skill_gap",
    "training_max_skill_gap",
    "phase",
    "role_revenue",
    "required_person_month",
    "request_months",
    "evidence_case_ids",
    "grounding_score",
    "comment",
  ],
  staff_preference_options: [
    "preference_option_code",
    "staff_code",
    "period_code",
    "opportunity_code",
    "opportunity_request_code",
    "role_code",
    "assignment_type",
    "eligibility_status",
    "skill_gap",
    "allocation_percentage",
    "request_headcount",
    "request_training_slots",
    "request_total_slots",
    "theme",
    "mentor_available",
    "score",
    "reason",
    "start_period_code",
    "end_period_code",
    "preference_status",
    "comment",
  ],
  staff_preference_submissions: [
    "submission_code",
    "staff_code",
    "period_code",
    "choice_type",
    "preference_option_code",
    "training_role_code",
    "opportunity_code",
    "opportunity_request_code",
    "role_code",
    "assignment_type",
    "allocation_percentage",
    "preference_status",
    "comment",
    "submitted_at",
  ],
  assignment_recommendations: [
    "assignment_recommendation_code",
    "staff_code",
    "opportunity_request_code",
    "slot",
    "assignment_type",
    "matching_reason",
    "comment",
  ],
};

export default function PipelineExecutionScreen() {
  const { data, loading, error } = useAppData();
  const approval = useApprovalState();
  const [tables, setTables] = useState<PipelineTables>({});
  const [stage, setStage] = useState<Stage>("loaded");
  const [selectedTable, setSelectedTable] = useState("theme_recommendations");
  const [running, setRunning] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) return;
    setTables({ ...data.sample, ...data.planning });
  }, [data]);

  const summary = useMemo(
    () => ({
      salesPlanRevenue: sumBy(tables.sales_plans ?? [], "target_revenue"),
      themeRevenue: sumBy(tables.theme_recommendations ?? [], "planned_revenue"),
      projectRevenue: sumBy(tables.project_sizing_recommendations ?? [], "estimated_revenue"),
      opportunities: tables.opportunities?.length ?? 0,
      requests: tables.opportunity_requests?.length ?? 0,
      assignments: tables.opportunity_assignments?.length ?? 0,
    }),
    [tables],
  );

  const workflowSteps = useMemo(
    () => workflowStepperRows(workflowNodesFromTables(tables, approval.records)),
    [tables, approval.records],
  );

  if (loading) return <p>Loading local artifact...</p>;
  if (error) return <p role="alert">Data load error: {error}</p>;

  async function run(label: string, endpoint: string) {
    setRunning(label);
    setRunError(null);
    try {
      const response = await runWorkflowEndpoint(endpoint, tables, approval.approvalsPayload());
      setTables(response.tables);
      setStage(String(response.metadata?.stage ?? stage) as Stage);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(null);
    }
  }

  function updateTable(tableName: string, rows: Row[]) {
    setTables((current) => {
      const next = { ...current, [tableName]: rows };
      writeSessionTables(next);
      return next;
    });
  }

  return (
    <div className="grid">
      <HITLStageHeader
        owner="管理"
        canEdit={["検証用Pipelineの手動実行", "browser session上のTable編集"]}
        canView={["SubPipeline入出力", "Workflow状態", "各TableのBI概要"]}
      />
      {runError ? <p role="alert" className="error-text">{runError}</p> : null}
      <WorkflowStepper steps={workflowSteps} />

      <section className="panel admin-debug-panel">
        <h2>Admin Pipeline Sandbox</h2>
        <p className="muted">
          管理者向けの検証画面です。通常の稟議承認は各担当画面で行います。この画面のTable編集はsession dataだけを変更し、承認履歴は更新しません。
        </p>
        <div className="toolbar">
          <button disabled={!!running} onClick={() => run("Propose Theme/Solution", endpoints.theme)}>Propose Theme/Solution</button>
          <button disabled={!!running} onClick={() => run("Propose Project/Requests", endpoints.project)}>Propose Project/Requests</button>
          <button disabled={!!running} onClick={() => run("Materialize", endpoints.materialize)}>Materialize</button>
          <button disabled={!!running} onClick={() => run("Preference Options", endpoints.preferenceOptions)}>Preference Options</button>
          <button disabled={!!running} onClick={() => run("Propose Assignments", endpoints.assignments)}>Propose Assignments</button>
          <button disabled={!!running} onClick={() => run("Finalize Assignments", endpoints.finalize)}>Finalize Assignments</button>
        </div>
        <p>Current stage: <StatusBadge status={stage} /> {running ? `Running ${running}...` : ""}</p>
      </section>

      <div className="grid cols-3">
        <MetricCard label="SalesPlan Revenue" value={formatCurrency(summary.salesPlanRevenue)} />
        <MetricCard label="Theme Revenue" value={formatCurrency(summary.themeRevenue)} />
        <MetricCard label="Project Revenue" value={formatCurrency(summary.projectRevenue)} />
        <MetricCard label="Opportunities" value={summary.opportunities} />
        <MetricCard label="Requests" value={summary.requests} />
        <MetricCard label="Assignments" value={summary.assignments} />
      </div>

      <section className="panel">
        <h2>Table Workspace</h2>
        <div className="toolbar">
          <label className="field">
            Table
            <select value={selectedTable} onChange={(event) => setSelectedTable(event.target.value)}>
              {reviewTables.map((tableName) => (
                <option key={tableName} value={tableName}>
                  {tableName}
                </option>
              ))}
            </select>
          </label>
          <StatusBadge status={approval.statusOf(selectedTable)} />
        </div>
        <TableWorkspace
          tableName={selectedTable}
          rows={tables[selectedTable] ?? []}
          onChange={(rows) => updateTable(selectedTable, rows)}
        />
      </section>
    </div>
  );
}

function TableWorkspace({
  tableName,
  rows,
  onChange,
}: {
  tableName: string;
  rows: Row[];
  onChange: (rows: Row[]) => void;
}) {
  const columns = tableColumns[tableName] ?? inferColumns(rows);
  const revenueKey = columns.find((column) => column.includes("revenue"));
  const groupedKey = columns.find((column) => column.endsWith("_code")) ?? columns[0];

  function rowKey(row: Row, index: number) {
    return String(row.code ?? row.project_spec_code ?? row.request_recommendation_code ?? row.assignment_recommendation_code ?? index);
  }

  function addRow() {
    onChange([...rows, Object.fromEntries(columns.map((column) => [column, ""]))]);
  }

  function deleteLastRow() {
    onChange(rows.slice(0, Math.max(0, rows.length - 1)));
  }

  return (
    <div className="grid">
      <div className="grid cols-3">
        <MetricCard label="Rows" value={rows.length} />
        <MetricCard label="Columns" value={columns.length} />
        <MetricCard label="Revenue Sum" value={formatCurrency(revenueKey ? sumBy(rows, revenueKey) : 0)} description={revenueKey ?? "no revenue column"} />
      </div>
      {groupedKey ? (
        <SimpleBarChart
          title={`${tableName}: ${groupedKey}`}
          rows={
            revenueKey
              ? groupSumRows(rows, groupedKey, revenueKey)
              : groupCountRows(rows, groupedKey)
          }
          valueFormatter={revenueKey ? formatCurrency : undefined}
        />
      ) : null}
      <div className="toolbar">
        <button onClick={addRow}>Add Row</button>
        <button className="secondary" onClick={deleteLastRow}>Delete Last Row</button>
      </div>
      <Suspense fallback={<p className="muted">Loading table editor...</p>}>
        <DataFrameGrid
          rows={rows}
          rowKey={rowKey}
          onRowsChange={onChange}
          columns={columns.map((column) => ({
            key: column,
            label: column,
            type: numericField(column) ? "number" : "text",
          }))}
        />
      </Suspense>
    </div>
  );
}

function inferColumns(rows: Row[]): string[] {
  return Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
}

function numericField(field: string): boolean {
  return field.endsWith("revenue") || field.endsWith("months") || field.includes("headcount") || field.includes("percentage") || field.includes("slots") || field.includes("gap") || field.includes("rank") || field.includes("score");
}
