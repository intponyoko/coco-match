import { useMemo, useState } from "react";
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { Bar, Doughnut } from "react-chartjs-2";
import AgentAssistSummary from "../../components/AgentAssistSummary";
import AICopilotPanel from "../../components/AICopilotPanel";
import EvidencePanel from "../../components/EvidencePanel";
import HITLStageHeader from "../../components/HITLStageHeader";
import MetricCard from "../../components/MetricCard";
import RawDataDisclosure from "../../components/RawDataDisclosure";
import StatusBadge from "../../components/StatusBadge";
import SubmissionProgress from "../../components/SubmissionProgress";
import type { AgentResponse } from "../../lib/apiClient";
import { useApprovalState } from "../../lib/approvalState";
import { chartColor } from "../../lib/chartColors";
import { byCode, rows, sumBy, useAppData, type Row } from "../../lib/data";
import { formatCurrency } from "../../lib/formatting";
import { labelFromMap, labelRows } from "../../lib/labels";
import { uniqueStringValues } from "../../lib/rowUtils";
import { saveSessionTable, sessionRows } from "../../lib/tableSession";
import { groupSumRows } from "../../lib/tableMetrics";
import { useAICopilot } from "../../lib/useAICopilot";
import { approveTable as approvedPayload, runAgentWorkflowEndpoint, runWorkflowEndpoint, tablesFromAppData } from "../../lib/workflowRunner";

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Legend,
  LinearScale,
  Tooltip,
);

type Tab = "theme" | "scale";

type OpportunityRequestsScreenProps = {
  initialTab?: Tab;
  fixedTab?: boolean;
};

const MIN_SUBMISSION_PROGRESS_MS = 450;

export default function OpportunityRequestsScreen({
  initialTab = "theme",
  fixedTab = false,
}: OpportunityRequestsScreenProps) {
  const { data, loading, error } = useAppData();
  const approval = useApprovalState();
  const [tab, setTab] = useState<Tab>(initialTab);
  const [running, setRunning] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [agentResponse, setAgentResponse] = useState<AgentResponse | null>(null);
  const [editedThemes, setEditedThemes] = useState<Row[] | null>(null);
  const [editedSpecs, setEditedSpecs] = useState<Row[] | null>(null);
  const [editedRequests, setEditedRequests] = useState<Row[] | null>(null);
  const [selectedThemeKey, setSelectedThemeKey] = useState("");
  const [selectedProjectKey, setSelectedProjectKey] = useState("");
  const [editingProjectIndex, setEditingProjectIndex] = useState<number | null>(null);

  const themes = editedThemes ?? sessionRows(data, "planning", "theme_recommendations");
  const specs = editedSpecs ?? sessionRows(data, "planning", "project_sizing_recommendations");
  const requests = editedRequests ?? sessionRows(data, "planning", "request_recommendations");
  const roleOptions = rows(data, "sample", "roles");
  const rolesByCode = byCode(roleOptions);
  const industriesByCode = byCode(rows(data, "sample", "industries"));
  const solutionsByCode = byCode(rows(data, "sample", "solutions"));
  const salesPlans = rows(data, "sample", "sales_plans");
  const themeNodes = rows(data, "planning", "knowledge_nodes");
  const themeEdges = rows(data, "planning", "knowledge_edges");
  const projectNodes = rows(data, "planning", "project_knowledge_nodes");
  const projectEdges = rows(data, "planning", "project_knowledge_edges");
  const nodes = tab === "scale" && projectNodes.length > 0 ? projectNodes : themeNodes;
  const edges = tab === "scale" && projectEdges.length > 0 ? projectEdges : themeEdges;
  const retrievedEvidenceChunks = rows(data, "planning", "retrieved_evidence_chunks");
  const solutionOptions = useMemo(
    () => Array.from(new Set(themes.map((row) => String(row.solution_code ?? "")).filter(Boolean))).sort(),
    [themes],
  );
  const selectedThemeIndex = useMemo(() => {
    const index = themes.findIndex((row, rowIndex) => themeKey(row, rowIndex) === selectedThemeKey);
    return index >= 0 ? index : 0;
  }, [themes, selectedThemeKey]);
  const selectedTheme = themes[selectedThemeIndex];
  const selectedProjectIndex = useMemo(() => {
    const index = specs.findIndex((row, rowIndex) => projectKey(row, rowIndex) === selectedProjectKey);
    return index >= 0 ? index : 0;
  }, [specs, selectedProjectKey]);
  const timelinePeriods = useMemo(
    () => timelinePeriodCodes(specs),
    [specs],
  );

  const impact = useMemo(
    () => ({
      themeCount: themes.length,
      themeRevenue: sumBy(themes, "planned_revenue"),
      projectCount: specs.length,
      projectRevenue: sumBy(specs, "estimated_revenue"),
      requestCount: requests.length,
      requestHeadcount: sumBy(requests, "headcount"),
      trainingSlots: sumBy(requests, "training_slots"),
    }),
    [themes, specs, requests],
  );
  const consistencyMetrics = useMemo(
    () => buildConsistencyMetrics(salesPlans, themes, specs, requests),
    [requests, salesPlans, specs, themes],
  );
  const projectReviewIssues = useMemo(
    () => buildProjectReviewIssues(specs, requests),
    [requests, specs],
  );
  const themeCoverageMetric = consistencyMetrics.find(
    (row) => String(row.metric_name ?? "") === "theme_revenue_coverage" && String(row.metric_scope ?? "") === "global",
  );
  const industryMismatchCount = consistencyMetrics.filter(
    (row) => String(row.metric_name ?? "") === "theme_revenue_coverage"
      && String(row.metric_scope ?? "").startsWith("industry:")
      && Math.abs(Number(row.delta_value ?? 0)) > 0.5,
  ).length;
  const stage = tab === "theme" ? "theme_solution" : "project_request";
  const copilot = useAICopilot({
    enabled: Boolean(data),
    payload: data ? {
      tables: {
        ...tablesFromAppData(data),
        theme_recommendations: themes,
        project_sizing_recommendations: specs,
        request_recommendations: requests,
        consistency_metrics: consistencyMetrics,
        project_review_issues: projectReviewIssues,
      },
      approvals: approval.approvalsPayload(),
      stage,
      focus: tab === "theme"
        ? {
            sales_plan_code: selectedTheme?.sales_plan_code ?? "",
            theme: selectedTheme?.theme ?? "",
            solution_code: selectedTheme?.solution_code ?? "",
          }
        : {
            project_spec_code: specs[selectedProjectIndex]?.project_spec_code ?? "",
          },
    } : null,
  });

  if (loading) return <p>Loading app data...</p>;
  if (error) return <p role="alert">Data load error: {error}</p>;

  async function approveThemeTable() {
    const startedAt = performance.now();
    setRunning("project");
    setRunError(null);
    await waitForNextPaint();
    try {
      const response = await runAgentWorkflowEndpoint(
        "/agent/project-requests/propose",
        { ...tablesFromAppData(data), theme_recommendations: themes },
        approvedPayload({}, "theme_recommendations", "department", ""),
      );
      setAgentResponse(response);
      approval.setTableApproval("theme_recommendations", "approved", "department", "");
      window.location.href = "/";
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      await waitForMinimumProgress(startedAt);
      setRunning(null);
    }
  }

  async function approveProjectAndRequests() {
    setRunning("materialize");
    setRunError(null);
    try {
      const approvals = approvedPayload(
        approvedPayload({}, "project_sizing_recommendations", "department", ""),
        "request_recommendations",
        "department",
        "",
      );
      const materialized = await runWorkflowEndpoint(
        "/pipeline/materialize-opportunities",
        {
          ...tablesFromAppData(data),
          theme_recommendations: themes,
          project_sizing_recommendations: specs,
          request_recommendations: requests,
        },
        approvals,
      );
      const response = await runAgentWorkflowEndpoint(
        "/agent/career-plan/propose",
        materialized.tables,
        materialized.approvals ?? approvals,
      );
      setAgentResponse(response);
      approval.setTableApproval("project_sizing_recommendations", "approved", "department", "");
      approval.setTableApproval("request_recommendations", "approved", "department", "");
      window.location.href = "/";
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(null);
    }
  }

  function updateThemeRows(nextRows: Row[]) {
    setEditedThemes(nextRows);
    saveSessionTable(data, "theme_recommendations", nextRows);
    approval.setTableApproval("theme_recommendations", "edited", "department", "Edited in Theme/Solution table.");
  }

  function updateSelectedTheme(field: string, value: string | number) {
    if (!selectedTheme) {
      return;
    }
    updateThemeRows(
      themes.map((row, index) =>
        index === selectedThemeIndex ? { ...row, [field]: value } : row,
      ),
    );
  }

  function addTheme() {
    const nextRank = Math.max(0, ...themes.map((row) => Number(row.theme_rank ?? 0))) + 1;
    const base = selectedTheme ?? themes[0] ?? {};
    const newRow = {
      ...base,
      sales_plan_code: String(base.sales_plan_code ?? "PORT-CAND-MANUAL"),
      industry_code: String(base.industry_code ?? ""),
      theme_rank: nextRank,
      theme: "新しいTheme",
      planned_revenue: 0,
      customer_pain: "",
      evidence_case_ids: "",
    };
    updateThemeRows([...themes, newRow]);
  }

  function deleteSelectedTheme() {
    if (!selectedTheme || themes.length === 0) {
      return;
    }
    updateThemeRows(themes.filter((_, index) => index !== selectedThemeIndex));
    setSelectedThemeKey("");
  }

  function updateSpecRows(nextRows: Row[]) {
    setEditedSpecs(nextRows);
    saveSessionTable(data, "project_sizing_recommendations", nextRows);
    approval.setTableApproval("project_sizing_recommendations", "edited", "department", "Edited in Project Scale table.");
  }

  function updateRequestRows(nextRows: Row[]) {
    setEditedRequests(nextRows);
    saveSessionTable(data, "request_recommendations", nextRows);
    approval.setTableApproval("request_recommendations", "edited", "department", "Edited in Request table.");
  }

  return (
    <div className="grid">
      <HITLStageHeader
        owner="部署層"
        canEdit={["Theme/Solution Tableの編集・承認", "PJ規模とRequest Tableの編集・承認"]}
        canView={["SalesPlan coverage", "過去事例Evidence", "編集後のFTE需要"]}
        workflow={{
          step: tab === "theme" ? 2 : 3,
          status:
            tab === "theme"
              ? approval.statusOf("theme_recommendations")
              : combinedStatus([
                  approval.statusOf("project_sizing_recommendations"),
                  approval.statusOf("request_recommendations"),
                ]),
          prerequisite:
            tab === "theme"
              ? "SalesPlanが承認され、Theme/Solution候補が生成されていること"
              : "Theme/Solution Tableが承認され、Project/Request候補が生成されていること",
          nextAction:
            tab === "theme"
              ? "Account / PJ規模 / Request候補を生成"
              : "Opportunity / OpportunityRequestをMaterializeし、個人希望候補を生成",
        }}
      />
      <section className="panel impact-bi">
        <h2>Impact BI</h2>
        <div className="grid cols-3">
          <MetricCard label="Theme Revenue" value={formatCurrency(impact.themeRevenue)} description={`${impact.themeCount} themes`} />
          <MetricCard
            label="Theme Delta"
            value={formatCurrency(Number(themeCoverageMetric?.delta_value ?? 0))}
            description={themeCoverageMetric ? String(themeCoverageMetric.summary ?? "") : "SalesPlanとの差分"}
          />
          <MetricCard label="Industry Mismatch" value={industryMismatchCount} description="industry coverage gaps" />
          {tab === "theme" ? (
            <>
              <MetricCard label="Project Revenue" value="TBA" description="Theme承認後にPJ規模を計算" className="tba" />
              <MetricCard label="Request Headcount" value="TBA" description="Request生成後に反映" className="tba" />
              <MetricCard label="Projects Needing Review" value="TBA" description="PJ/Request生成後に判定" className="tba" />
            </>
          ) : (
            <>
              <MetricCard label="Project Revenue" value={formatCurrency(impact.projectRevenue)} description={`${impact.projectCount} projects`} />
              <MetricCard label="Request Headcount" value={impact.requestHeadcount} description={`${impact.requestCount} request rows / training ${impact.trainingSlots}`} />
              <MetricCard label="Projects Needing Review" value={projectReviewIssues.length} description="missing requests / invalid HC" />
            </>
          )}
        </div>
        <div className="grid cols-2">
          <ThemeRevenueChart rows={labelRows(groupSumRows(themes, "solution_code", "planned_revenue"), solutionsByCode)} />
          {tab === "theme" ? (
            <TbaChartCard
              title="Request Headcount"
              body="Theme承認後にRole別 headcount を計算します。現段階では downstream BI を確定させません。"
            />
          ) : (
            <RequestHeadcountChart rows={labelRows(groupSumRows(requests, "role_code", "headcount"), rolesByCode)} />
          )}
        </div>
        {tab === "scale" && projectReviewIssues.length > 0 ? (
          <section className="panel">
            <h3>Consistency Watchouts</h3>
            <ul className="compact-list">
              {projectReviewIssues.slice(0, 6).map((issue, index) => (
                <li key={`${String(issue.project_spec_code ?? "issue")}:${index}`}>
                  <strong>{String(issue.theme ?? issue.project_spec_code ?? "Project")}</strong>
                  <span>{String(issue.summary ?? "")}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </section>
      {!fixedTab ? (
        <div className="tabs" role="tablist" aria-label="Opportunity request approval tabs">
          <button className="tab-button" aria-selected={tab === "theme"} onClick={() => setTab("theme")}>Theme / Solution</button>
          <button className="tab-button" aria-selected={tab === "scale"} onClick={() => setTab("scale")}>Account / Scale / Request</button>
        </div>
      ) : null}
      {runError ? <p role="alert" className="error-text">{runError}</p> : null}

      {tab === "theme" ? (
        <section className="panel portfolio-review">
          <div className="toolbar">
            <div>
              <h2>Opportunity Portfolio Review</h2>
              <p className="muted">
                Theme/Solution候補をカードで確認し、選択中の候補だけをフォームで調整します。表は元データ確認用に折りたたんでいます。
              </p>
            </div>
            <StatusBadge status={approval.statusOf("theme_recommendations")} />
          </div>
          <div className="toolbar">
            <button className="secondary" type="button" onClick={addTheme}>カードを追加</button>
            <button className="secondary" type="button" disabled={!selectedTheme} onClick={deleteSelectedTheme}>選択中のカードを削除</button>
          </div>
          <div className="portfolio-layout">
            <div className="portfolio-card-list" aria-label="Opportunity portfolio candidates">
              {themes.map((row, index) => {
                const key = themeKey(row, index);
                const selected = index === selectedThemeIndex;
                return (
                  <button
                    className={`portfolio-card ${selected ? "selected" : ""}`}
                    type="button"
                    aria-pressed={selected}
                    key={key}
                    onClick={() => setSelectedThemeKey(key)}
                  >
                    <span className="portfolio-card-meta">
                      {labelFromMap(industriesByCode, row.industry_code)} / {labelFromMap(solutionsByCode, row.solution_code)}
                    </span>
                    <strong>{String(row.theme ?? "Untitled theme")}</strong>
                    <span>{formatCurrency(Number(row.planned_revenue ?? 0))}</span>
                    <small>{String(row.customer_pain ?? "")}</small>
                  </button>
                );
              })}
            </div>
            <div className="portfolio-detail">
              {selectedTheme ? (
                <>
                  <div className="grid cols-2">
                    <label className="field">
                      Theme
                      <input
                        value={String(selectedTheme.theme ?? "")}
                        onChange={(event) => updateSelectedTheme("theme", event.target.value)}
                      />
                    </label>
                    <label className="field">
                      Solution
                      <select
                        value={String(selectedTheme.solution_code ?? "")}
                        onChange={(event) => updateSelectedTheme("solution_code", event.target.value)}
                      >
                        {solutionOptions.map((solution) => (
                          <option key={solution} value={solution}>{labelFromMap(solutionsByCode, solution)}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Revenue
                      <input
                        type="number"
                        value={Number(selectedTheme.planned_revenue ?? 0)}
                        onChange={(event) => updateSelectedTheme("planned_revenue", Number(event.target.value))}
                      />
                    </label>
                    <label className="field">
                      Rank
                      <input
                        type="number"
                        value={Number(selectedTheme.theme_rank ?? 0)}
                        onChange={(event) => updateSelectedTheme("theme_rank", Number(event.target.value))}
                      />
                    </label>
                  </div>
                  <label className="field">
                    Customer pain
                    <textarea
                      value={String(selectedTheme.customer_pain ?? "")}
                      onChange={(event) => updateSelectedTheme("customer_pain", event.target.value)}
                      rows={3}
                    />
                  </label>
                  <EvidencePanel
                    evidenceCaseIds={String(selectedTheme.evidence_case_ids ?? "")}
                    nodes={nodes}
                    edges={edges}
                    retrievedEvidenceRows={retrievedEvidenceChunks}
                  />
                </>
              ) : (
                <p className="muted">Theme/Solution候補はまだありません。</p>
              )}
            </div>
          </div>
          <RawDataDisclosure
            title="元データをDataFrameで確認"
            rows={themes}
            columns={[
              { key: "sales_plan_code", label: "Portfolio" },
              { key: "industry_code", label: "Industry" },
              { key: "theme_rank", label: "Rank" },
              { key: "theme", label: "Theme" },
              { key: "solution_code", label: "Solution" },
              { key: "planned_revenue", label: "Revenue" },
              { key: "customer_pain", label: "Pain" },
              { key: "evidence_case_ids", label: "Evidence" },
            ]}
          />
          {runError ? <p role="alert" className="error-text">{runError}</p> : null}
          <AgentAssistSummary response={agentResponse} />
        </section>
      ) : null}

      {tab === "theme" ? (
        <section className="panel approval-panel">
          <h2>承認</h2>
          <p className="muted">このPortfolioを承認すると、次工程のAccount / PJ規模 / Request候補が生成されます。</p>
          {copilot.available ? (
            <AICopilotPanel
              response={copilot.response}
              loading={copilot.loading}
              error={copilot.error}
              onRefresh={copilot.refresh}
            />
          ) : null}
          {running === "project" ? (
            <SubmissionProgress
              title="Proposing Project / Request"
              body="承認済みPortfolioからAccount、PJ規模、Request候補を再計算しています。"
            />
          ) : null}
          {runError ? <p role="alert" className="error-text">{runError}</p> : null}
          <AgentAssistSummary response={agentResponse} />
          <div className="toolbar action-toolbar">
            <button disabled={!!running || themes.length === 0} onClick={approveThemeTable}>承認する</button>
          </div>
        </section>
      ) : (
        <div className="grid">
          <section className="panel project-request-review">
            <div className="toolbar">
              <div>
                <h2>Project / Request Approval</h2>
                <p className="muted">
                  PJ候補をカードで選択し、Account・規模・期間・Role別Requestをフォームで調整します。
                </p>
              </div>
              <StatusBadge
                status={combinedStatus([
                  approval.statusOf("project_sizing_recommendations"),
                  approval.statusOf("request_recommendations"),
                ])}
              />
            </div>
            <div className="project-planning-layout">
              <ProjectTimeline
                periods={timelinePeriods}
                projects={specs}
                requests={requests}
                solutionsByCode={solutionsByCode}
                selectedIndex={selectedProjectIndex}
                onSelect={(index) => {
                  setSelectedProjectKey(projectKey(specs[index], index));
                  setEditingProjectIndex(index);
                }}
              />
            </div>
            {editingProjectIndex !== null && specs[editingProjectIndex] ? (
              <ProjectEditModal
                project={specs[editingProjectIndex]}
                requests={requests.reduce<Row[]>((matched, request, requestIndex) => {
                  if (
                    String(request["project_spec_code"] ?? "") ===
                    String(specs[editingProjectIndex]["project_spec_code"] ?? "")
                  ) {
                    matched.push({ ...request, __requestIndex: requestIndex });
                  }
                  return matched;
                }, [])}
                roleOptions={roleOptions}
                rolesByCode={rolesByCode}
                solutionsByCode={solutionsByCode}
                phaseOptions={uniqueStringValues(requests, "phase")}
                nodes={nodes}
                edges={edges}
                retrievedEvidenceRows={retrievedEvidenceChunks}
                onClose={() => setEditingProjectIndex(null)}
                onChange={(field, value) => {
                  updateSpecRows(
                    specs.map((row, rowIndex) =>
                      rowIndex === editingProjectIndex ? { ...row, [field]: value } : row,
                    ),
                  );
                }}
                onRequestChange={(requestIndex, field, value) => {
                  updateRequestRows(
                    requests.map((row, rowIndex) =>
                      rowIndex === requestIndex ? { ...row, [field]: value } : row,
                    ),
                  );
                }}
              />
            ) : null}
            <div className="grid cols-2">
              <RawDataDisclosure
                title="Project Scale元データをDataFrameで確認"
                rows={specs}
                columns={[
                  { key: "project_spec_code", label: "Project" },
                  { key: "sales_plan_code", label: "Portfolio" },
                  { key: "industry_code", label: "Industry" },
                  { key: "account_code", label: "Account Code" },
                  { key: "account_name", label: "Account" },
                  { key: "theme", label: "Theme" },
                  { key: "solution_code", label: "Solution" },
                  { key: "start_period_code", label: "Start" },
                  { key: "estimated_revenue", label: "Revenue" },
                  { key: "duration_months", label: "Months" },
                  { key: "project_training_max_skill_gap", label: "PJ Gap" },
                ]}
              />
              <RawDataDisclosure
                title="Request元データをDataFrameで確認"
                rows={requests}
                columns={[
                  { key: "request_recommendation_code", label: "Request" },
                  { key: "project_spec_code", label: "Project" },
                  { key: "start_period_code", label: "Start" },
                  { key: "end_period_code", label: "End" },
                  { key: "role_code", label: "Role" },
                  { key: "headcount", label: "Headcount" },
                  { key: "allocation_percentage", label: "Allocation" },
                  { key: "training_slots", label: "Training" },
                  { key: "training_max_skill_gap", label: "Gap" },
                  { key: "phase", label: "Phase" },
                ]}
              />
            </div>
          </section>
          <section className="panel">
            <h2>Approval Action</h2>
            <p className="muted">編集済みのProject Scale TableとRequest Tableをまとめて次のPipelineへ渡します。</p>
            {copilot.available ? (
              <AICopilotPanel
                response={copilot.response}
                loading={copilot.loading}
                error={copilot.error}
                onRefresh={copilot.refresh}
              />
            ) : null}
            {running === "materialize" ? (
              <SubmissionProgress
                title="Materializing Opportunities"
                body="ProjectとRequestをOpportunityへ反映し、次の個人候補生成に渡す準備をしています。"
              />
            ) : null}
            <div className="toolbar action-toolbar">
              <button disabled={!!running} onClick={approveProjectAndRequests}>承認する</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function themeKey(row: Row, index: number) {
  return `${String(row.sales_plan_code ?? "")}:${String(row.theme_rank ?? "")}:${index}`;
}

function projectKey(row: Row, index: number) {
  return `${String(row.project_spec_code ?? "")}:${index}`;
}

function combinedStatus(statuses: string[]) {
  if (statuses.every((status) => status === "approved")) {
    return "approved";
  }
  if (statuses.includes("edited")) {
    return "edited";
  }
  if (statuses.includes("draft")) {
    return "draft";
  }
  return "pending";
}

async function waitForNextPaint() {
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

async function waitForMinimumProgress(startedAt: number) {
  const remaining = MIN_SUBMISSION_PROGRESS_MS - (performance.now() - startedAt);
  if (remaining <= 0) {
    return;
  }
  await new Promise<void>((resolve) => {
    window.setTimeout(resolve, remaining);
  });
}

function ProjectTimeline({
  periods,
  projects,
  requests,
  solutionsByCode,
  selectedIndex,
  onSelect,
}: {
  periods: string[];
  projects: Row[];
  requests: Row[];
  solutionsByCode: Map<string, Row>;
  selectedIndex: number;
  onSelect: (index: number) => void;
}) {
  if (projects.length === 0) {
    return <p className="muted">PJ候補はまだありません。</p>;
  }
  const monthTrack = `${PROJECT_LABEL_WIDTH}px repeat(${periods.length}, ${MONTH_COLUMN_WIDTH}px)`;
  return (
    <section className="timeline-panel" aria-label="Project timeline">
      <div
        className="timeline-header"
        style={{ gridTemplateColumns: monthTrack }}
      >
        <div className="timeline-corner">Project</div>
        {periods.map((period) => (
          <div className="timeline-month" key={period}>{period.slice(5)}</div>
        ))}
      </div>
      <div className="timeline-body">
        {projects.map((project, index) => {
          const placement = projectPlacement(project, periods);
          const projectRequests = requests.filter(
            (request) => String(request.project_spec_code ?? "") === String(project.project_spec_code ?? ""),
          );
          const selected = index === selectedIndex;
          const color = timelineColor(String(project.solution_code ?? ""));
          return (
            <div
              className={`timeline-row ${selected ? "selected" : ""}`}
              key={projectKey(project, index)}
              style={{ gridTemplateColumns: monthTrack }}
            >
              <button className="timeline-row-label" type="button" style={{ gridColumn: 1, gridRow: 1 }} onClick={() => onSelect(index)}>
                <strong>{String(project.account_name ?? project.account_code ?? "Account TBD")}</strong>
                <span>{labelFromMap(solutionsByCode, project.solution_code)} / {formatCurrency(Number(project.estimated_revenue ?? 0))}</span>
              </button>
              {periods.map((period, periodIndex) => (
                <div
                  className="timeline-cell"
                  key={`${projectKey(project, index)}:${period}`}
                  style={{ gridColumn: periodIndex + 2, gridRow: 1 }}
                />
              ))}
              <div
                className={`timeline-project-bar ${selected ? "selected" : ""}`}
                role="button"
                tabIndex={0}
                style={{
                  gridColumn: `${placement.start + 1} / span ${placement.span}`,
                  background: color,
                }}
                onClick={() => onSelect(index)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(index);
                  }
                }}
              >
                <strong>{String(project.theme ?? "")}</strong>
                <span>{projectRequests.length} requests</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  const boundedValue = Math.min(max, Math.max(min, Number.isFinite(value) ? value : min));
  return (
    <label className="field range-field">
      <span>
        {label}
        <strong>{boundedValue}</strong>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={boundedValue}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function selectOptionsWithCurrent(
  options: { value: string; label: string }[],
  current: string,
) {
  const knownValues = new Set(options.map((option) => option.value));
  const normalizedOptions = options.filter((option) => option.value);
  if (!current) {
    return [{ value: "", label: "未設定" }, ...normalizedOptions];
  }
  if (knownValues.has(current)) {
    return normalizedOptions;
  }
  return [{ value: current, label: current }, ...normalizedOptions];
}

function ProjectEditModal({
  project,
  requests,
  roleOptions,
  rolesByCode,
  solutionsByCode,
  phaseOptions,
  nodes,
  edges,
  retrievedEvidenceRows,
  onChange,
  onRequestChange,
  onClose,
}: {
  project: Row;
  requests: Row[];
  roleOptions: Row[];
  rolesByCode: Map<string, Row>;
  solutionsByCode: Map<string, Row>;
  phaseOptions: string[];
  nodes: Row[];
  edges: Row[];
  retrievedEvidenceRows: Row[];
  onChange: (field: string, value: string | number) => void;
  onRequestChange: (requestIndex: number, field: string, value: string | number) => void;
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="project-edit-modal" role="dialog" aria-modal="true" aria-label="Project edit window">
        <div className="toolbar">
          <div>
            <h2>{String(project.account_name ?? project.account_code ?? "Account TBD")}</h2>
            <p className="muted">{labelFromMap(solutionsByCode, project.solution_code)} / {String(project.start_period_code ?? "")}</p>
          </div>
          <button className="secondary" type="button" onClick={onClose}>閉じる</button>
        </div>
        <div className="grid cols-3">
          <label className="field">
            Account code
            <input value={String(project.account_code ?? "")} onChange={(event) => onChange("account_code", event.target.value)} />
          </label>
          <label className="field">
            Account
            <input value={String(project.account_name ?? "")} onChange={(event) => onChange("account_name", event.target.value)} />
          </label>
          <label className="field">
            Revenue
            <input type="number" value={Number(project.estimated_revenue ?? 0)} onChange={(event) => onChange("estimated_revenue", Number(event.target.value))} />
          </label>
          <label className="field">
            Start month
            <input value={String(project.start_period_code ?? "")} onChange={(event) => onChange("start_period_code", event.target.value)} />
          </label>
          <label className="field">
            Duration
            <input type="number" value={Number(project.duration_months ?? 0)} onChange={(event) => onChange("duration_months", Number(event.target.value))} />
          </label>
          <label className="field">
            Training gap
            <input type="number" value={Number(project.project_training_max_skill_gap ?? 0)} onChange={(event) => onChange("project_training_max_skill_gap", Number(event.target.value))} />
          </label>
        </div>
        <label className="field">
          Theme
          <textarea value={String(project.theme ?? "")} onChange={(event) => onChange("theme", event.target.value)} rows={3} />
        </label>
        <section className="request-evidence-panel">
          <h3>Role設定</h3>
          <div className="request-evidence-grid">
            {requests.map((request, index) => (
              <article className="request-evidence-card" key={String(request.request_recommendation_code ?? index)}>
                <label className="field">
                  Role
                  <select
                    value={String(request.role_code ?? "")}
                    onChange={(event) => onRequestChange(Number(request.__requestIndex), "role_code", event.target.value)}
                  >
                    {selectOptionsWithCurrent(
                      roleOptions.map((role) => ({
                        value: String(role.code ?? ""),
                        label: labelFromMap(rolesByCode, role.code),
                      })),
                      String(request.role_code ?? ""),
                    ).map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Phase
                  <select
                    value={String(request.phase ?? "")}
                    onChange={(event) => onRequestChange(Number(request.__requestIndex), "phase", event.target.value)}
                  >
                    {selectOptionsWithCurrent(
                      phaseOptions.map((phase) => ({ value: phase, label: phase })),
                      String(request.phase ?? ""),
                    ).map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <SliderField
                  label="Headcount"
                  value={Number(request.headcount ?? 0)}
                  min={0}
                  max={5}
                  step={1}
                  onChange={(value) => onRequestChange(Number(request.__requestIndex), "headcount", value)}
                />
                <SliderField
                  label="Allocation %"
                  value={Number(request.allocation_percentage ?? 0)}
                  min={0}
                  max={100}
                  step={5}
                  onChange={(value) => onRequestChange(Number(request.__requestIndex), "allocation_percentage", value)}
                />
                <SliderField
                  label="Training slots"
                  value={Number(request.training_slots ?? 0)}
                  min={0}
                  max={5}
                  step={1}
                  onChange={(value) => onRequestChange(Number(request.__requestIndex), "training_slots", value)}
                />
                <SliderField
                  label="Training gap"
                  value={Number(request.training_max_skill_gap ?? 0)}
                  min={0}
                  max={10}
                  step={1}
                  onChange={(value) => onRequestChange(Number(request.__requestIndex), "training_max_skill_gap", value)}
                />
                <label className="field">
                  Start
                  <input
                    value={String(request.start_period_code ?? "")}
                    onChange={(event) => onRequestChange(Number(request.__requestIndex), "start_period_code", event.target.value)}
                  />
                </label>
                <label className="field">
                  End
                  <input
                    value={String(request.end_period_code ?? "")}
                    onChange={(event) => onRequestChange(Number(request.__requestIndex), "end_period_code", event.target.value)}
                  />
                </label>
              </article>
            ))}
          </div>
        </section>
        <EvidencePanel
          evidenceCaseIds={String(project.evidence_case_ids ?? "")}
          nodes={nodes}
          edges={edges}
          retrievedEvidenceRows={retrievedEvidenceRows}
        />
      </section>
    </div>
  );
}

const PROJECT_LABEL_WIDTH = 220;
const MONTH_COLUMN_WIDTH = 68;

function timelinePeriodCodes(projects: Row[]) {
  const codes = new Set<string>();
  for (const project of projects) {
    const start = String(project.start_period_code ?? "");
    const duration = sanitizedDuration(project.duration_months);
    if (start) {
      for (let i = 0; i < duration; i += 1) {
        codes.add(addMonths(start, i));
      }
    }
  }
  return Array.from(codes).sort();
}

function projectPlacement(project: Row, periods: string[]) {
  const start = String(project.start_period_code ?? periods[0] ?? "");
  const duration = sanitizedDuration(project.duration_months);
  return placement(start, duration, periods);
}

function placement(startCode: string, duration: number, periods: string[]) {
  const foundIndex = periods.indexOf(startCode);
  const index = foundIndex >= 0 ? foundIndex : 0;
  const remaining = Math.max(1, periods.length - index);
  const span = Math.max(1, Math.min(sanitizedDuration(duration), remaining));
  return { start: index + 1, span };
}

function addMonths(periodCode: string, months: number) {
  const date = new Date(`${periodCode}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return periodCode;
  }
  date.setMonth(date.getMonth() + months);
  return toPeriodCode(date);
}

function toPeriodCode(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-01`;
}

function sanitizedDuration(value: unknown) {
  const duration = Number(value);
  return Number.isFinite(duration) ? Math.max(1, Math.ceil(duration)) : 1;
}

function timelineColor(solutionCode: string) {
  const hash = Array.from(solutionCode).reduce((total, char) => total + char.charCodeAt(0), 0);
  return chartColor(hash);
}

type ChartRow = {
  label: string;
  value: number;
};

function ThemeRevenueChart({ rows }: { rows: ChartRow[] }) {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  const chartData: ChartData<"doughnut"> = {
    labels: rows.map((row) => row.label),
    datasets: [
      {
        data: rows.map((row) => row.value),
        backgroundColor: rows.map((_, index) => chartColor(index)),
        borderColor: "#ffffff",
        borderWidth: 2,
      },
    ],
  };
  const options: ChartOptions<"doughnut"> = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "62%",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context) => {
            const value = Number(context.parsed ?? 0);
            const percentage = ((value / Math.max(total, 1)) * 100).toFixed(1);
            return `${context.label}: ${formatCurrency(value)} (${percentage}%)`;
          },
        },
      },
    },
  };

  return (
    <section className="chart-card" aria-label="Theme revenue by solution">
      <h3>Theme Revenue by Solution</h3>
      <div className="industry-share">
        <div className="chartjs-donut-frame">
          <Doughnut data={chartData} options={options} />
        </div>
        <div className="industry-legend">
          {rows.map((row, index) => (
            <div className="legend-row" key={row.label}>
              <span className="legend-swatch" style={{ background: chartColor(index) }} />
              <strong>{row.label}</strong>
              <span>{formatCurrency(row.value)}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function RequestHeadcountChart({ rows }: { rows: ChartRow[] }) {
  const chartData: ChartData<"bar"> = {
    labels: rows.map((row) => row.label),
    datasets: [
      {
        label: "Headcount",
        data: rows.map((row) => row.value),
        backgroundColor: "#0017c1",
        borderColor: "#0017c1",
        borderWidth: 1,
      },
    ],
  };
  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
    },
    scales: {
      x: { grid: { display: false } },
      y: {
        beginAtZero: true,
        ticks: { precision: 0 },
      },
    },
  };

  return (
    <section className="chart-card" aria-label="Request headcount by role">
      <h3>Request Headcount by Role</h3>
      <div className="chartjs-frame">
        <Bar data={chartData} options={options} />
      </div>
    </section>
  );
}

function TbaChartCard({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <section className="panel metric-card tba">
      <h3>{title}</h3>
      <p className="muted">{body}</p>
    </section>
  );
}

function buildConsistencyMetrics(
  salesPlans: Row[],
  themes: Row[],
  projects: Row[],
  requests: Row[],
): Row[] {
  const salesTotal = sumNumbers(salesPlans, "target_revenue");
  const themeTotal = sumNumbers(themes, "planned_revenue");
  const rows: Row[] = [
    metricRow(
      "global",
      "theme_revenue_coverage",
      themeTotal,
      salesTotal,
      `Theme revenue ${formatCurrency(themeTotal)} against SalesPlan ${formatCurrency(salesTotal)}.`,
    ),
  ];
  const salesByIndustry = groupTotals(salesPlans, "industry_code", "target_revenue");
  const themeByIndustry = groupTotals(themes, "industry_code", "planned_revenue");
  for (const industryCode of new Set([...Object.keys(salesByIndustry), ...Object.keys(themeByIndustry)])) {
    rows.push(
      metricRow(
        `industry:${industryCode}`,
        "theme_revenue_coverage",
        themeByIndustry[industryCode] ?? 0,
        salesByIndustry[industryCode] ?? 0,
        `Industry ${industryCode} coverage check.`,
      ),
    );
  }
  rows.push(
    metricRow(
      "global",
      "project_count",
      projects.length,
      themes.length,
      `Generated ${projects.length} projects from ${themes.length} themes.`,
    ),
  );
  const positiveRequests = requests.filter((row) => Number(row.headcount ?? 0) > 0);
  rows.push(
    metricRow(
      "global",
      "positive_request_count",
      positiveRequests.length,
      requests.length,
      `Positive-headcount requests ${positiveRequests.length} / ${requests.length}.`,
    ),
  );
  return rows;
}

function buildProjectReviewIssues(projects: Row[], requests: Row[]): Row[] {
  return projects.flatMap((project) => {
    const projectCode = String(project.project_spec_code ?? "");
    const projectRequests = requests.filter(
      (row) => String(row.project_spec_code ?? "") === projectCode,
    );
    const positiveRequests = projectRequests.filter((row) => Number(row.headcount ?? 0) > 0);
    if (projectRequests.length === 0) {
      return [issueRow(project, "missing_requests", "No request rows were generated for this project proposal.")];
    }
    if (positiveRequests.length === 0) {
      return [issueRow(project, "non_positive_headcount", "All generated request rows have non-positive headcount.")];
    }
    return [];
  });
}

function metricRow(
  scope: string,
  name: string,
  metricValue: number,
  referenceValue: number,
  summary: string,
): Row {
  const deltaValue = metricValue - referenceValue;
  return {
    metric_scope: scope,
    metric_name: name,
    metric_value: metricValue,
    reference_value: referenceValue,
    delta_value: deltaValue,
    status: Math.abs(deltaValue) < 0.5 ? "ok" : "review",
    summary,
  };
}

function issueRow(project: Row, issueKind: string, summary: string): Row {
  return {
    project_spec_code: String(project.project_spec_code ?? ""),
    sales_plan_code: String(project.sales_plan_code ?? ""),
    theme: String(project.theme ?? ""),
    account_name: String(project.account_name ?? project.account_code ?? ""),
    issue_kind: issueKind,
    severity: "high",
    summary,
  };
}

function groupTotals(rows: Row[], key: string, valueKey: string): Record<string, number> {
  return rows.reduce<Record<string, number>>((totals, row) => {
    const groupKey = String(row[key] ?? "");
    totals[groupKey] = (totals[groupKey] ?? 0) + Number(row[valueKey] ?? 0);
    return totals;
  }, {});
}

function sumNumbers(rows: Row[], key: string): number {
  return rows.reduce((total, row) => total + Number(row[key] ?? 0), 0);
}
