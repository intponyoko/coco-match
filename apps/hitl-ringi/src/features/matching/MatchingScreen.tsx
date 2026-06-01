import { useState } from "react";
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
import AICopilotPanel from "../../components/AICopilotPanel";
import HITLStageHeader from "../../components/HITLStageHeader";
import MetricCard from "../../components/MetricCard";
import RawDataDisclosure from "../../components/RawDataDisclosure";
import StatusBadge from "../../components/StatusBadge";
import SubmissionProgress from "../../components/SubmissionProgress";
import { useApprovalState } from "../../lib/approvalState";
import { byCode, numberValue, rows, useAppData, type Row } from "../../lib/data";
import { managementSummary } from "../../lib/derivedMetrics";
import { formatNumber, formatPercent } from "../../lib/formatting";
import { labelFromMap } from "../../lib/labels";
import { saveSessionTable, sessionRows } from "../../lib/tableSession";
import { useAICopilot } from "../../lib/useAICopilot";
import { approveTable, runWorkflowEndpoint, tablesFromAppData } from "../../lib/workflowRunner";

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Legend,
  LinearScale,
  Tooltip,
);

export default function MatchingScreen() {
  const { data, loading, error } = useAppData();
  const approval = useApprovalState();
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [selectedProjectCode, setSelectedProjectCode] = useState("");
  const trace = rows(data, "planning", "matching_trace");
  const requests = rows(data, "planning", "opportunity_requests");
  const opportunities = rows(data, "planning", "opportunities");
  const staffs = rows(data, "sample", "staffs");
  const rolesByCode = byCode(rows(data, "sample", "roles"));
  const staffsByCode = byCode(staffs);
  const assignments = rows(data, "planning", "opportunity_assignments");
  const [draftRecommendations, setDraftRecommendations] = useState<Row[] | null>(null);
  const assignmentRecommendations =
    draftRecommendations ?? sessionRows(data, "planning", "assignment_recommendations");
  const utilization = rows(data, "planning", "staff_utilization");
  const summary = managementSummary(data);
  const matchingReview = buildMatchingReview({
    trace,
    requests,
    opportunities,
    staffs,
    utilization,
    assignmentRecommendations,
    rolesByCode,
    staffsByCode,
  });
  const selectedProject =
    matchingReview.projects.find((project) => project.code === selectedProjectCode)
    ?? matchingReview.projects[0];
  const copilot = useAICopilot({
    enabled: Boolean(data),
    payload: data ? {
      tables: {
        ...tablesFromAppData(data),
        assignment_recommendations: assignmentRecommendations,
      },
      approvals: approval.approvalsPayload(),
      stage: "matching",
      focus: {
        opportunity_code: selectedProject?.code ?? "",
      },
    } : null,
  });

  if (loading) return <p>Loading app data...</p>;
  if (error) return <p role="alert">Data load error: {error}</p>;

  async function approveRun() {
    setRunning(true);
    setRunError(null);
    try {
      await runWorkflowEndpoint(
        "/pipeline/finalize-assignments",
        { ...tablesFromAppData(data), assignment_recommendations: assignmentRecommendations },
        approveTable({}, "assignment_recommendations", "department", "Matching run reviewed in SSG UI."),
      );
      approval.setTableApproval("assignment_recommendations", "approved", "department", "Matching run reviewed in SSG UI.");
      window.location.href = "/";
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  function updateAssignmentRecommendations(nextRows: Row[]) {
    setDraftRecommendations(nextRows);
    saveSessionTable(data, "assignment_recommendations", nextRows);
    approval.setTableApproval("assignment_recommendations", "edited", "department", "Edited in Matching recommendation table.");
  }

  function updateAssignee(requestCode: string, slot: number, staffCode: string) {
    const existingIndex = assignmentRecommendations.findIndex(
      (row) =>
        String(row.opportunity_request_code ?? "") === requestCode
        && numberValue(row.slot) === slot,
    );
    if (!staffCode) {
      updateAssignmentRecommendations(
        assignmentRecommendations.filter((_, index) => index !== existingIndex),
      );
      return;
    }
    const nextRow = {
      assignment_recommendation_code: existingIndex >= 0
        ? String(assignmentRecommendations[existingIndex].assignment_recommendation_code ?? "")
        : `AREC-MANUAL-${requestCode}-${slot}`,
      staff_code: staffCode,
      opportunity_request_code: requestCode,
      slot,
      assignment_type: existingIndex >= 0
        ? String(assignmentRecommendations[existingIndex].assignment_type ?? "standard")
        : "standard",
      matching_reason: "department_manual_review",
      comment: existingIndex >= 0
        ? String(assignmentRecommendations[existingIndex].comment ?? "")
        : "Edited in Matching review.",
    };
    if (existingIndex >= 0) {
      updateAssignmentRecommendations(
        assignmentRecommendations.map((row, index) => index === existingIndex ? { ...row, ...nextRow } : row),
      );
      return;
    }
    updateAssignmentRecommendations([...assignmentRecommendations, nextRow]);
  }

  function updateAssignmentType(requestCode: string, slot: number, assignmentType: string) {
    updateAssignmentRecommendations(
      assignmentRecommendations.map((row) =>
        String(row.opportunity_request_code ?? "") === requestCode
          && numberValue(row.slot) === slot
          ? { ...row, assignment_type: assignmentType, matching_reason: "department_manual_review" }
          : row,
      ),
    );
  }

  return (
    <div className="grid">
      <HITLStageHeader
        owner="部署層"
        canEdit={["Matching案の編集・承認"]}
        canView={["assigned / tough assigned / unassigned", "Staff utilization", "Role別不足"]}
        workflow={{
          step: 5,
          status: approval.statusOf("assignment_recommendations", "draft"),
          prerequisite: "個人層が年間PJ希望・研修希望を提出し、Matching案が生成されていること",
          nextAction: "OpportunityAssignmentをFinalize",
        }}
      />
      <section className="panel matching-finalize-panel">
        <div>
          <h2>Matching最終確認</h2>
          <p className="muted">
            未割当・育成枠・稼働偏りを確認し、このMatching案をOpportunityAssignmentとして確定します。
          </p>
          {assignmentRecommendations.length === 0 ? (
            <p className="muted">Matching案はまだありません。4. Personal Interest の提出後に表示されます。</p>
          ) : null}
          {runError ? <p role="alert" className="error-text">{runError}</p> : null}
          {copilot.available ? (
            <AICopilotPanel
              response={copilot.response}
              loading={copilot.loading}
              error={copilot.error}
              onRefresh={copilot.refresh}
            />
          ) : null}
          {running ? (
            <SubmissionProgress
              title="Finalizing Assignments"
              body="承認済みMatching案をOpportunityAssignmentへ反映し、最終アサイン計画を確定しています。"
            />
          ) : null}
        </div>
        <div className="toolbar compact">
          <button disabled={running || assignmentRecommendations.length === 0} onClick={approveRun}>
            承認する
          </button>
        </div>
      </section>

      <section className="panel matching-bi-panel">
        <h2>Matching BI</h2>
        <div className="matching-metric-grid">
          <MetricCard label="Matching Rate" value={formatPercent(summary.matchingRate)} />
          <MetricCard label="Assigned Slots" value={matchingReview.assignedCount} description={`${matchingReview.toughAssignedCount} tough assigned`} />
          <MetricCard label="Unassigned Slots" value={matchingReview.unassignedCount} description={`${matchingReview.unassignedRoles.length} roles affected`} />
          <MetricCard label="平均稼働率" value={`${formatNumber(matchingReview.averageUtilization)}%`} description={`${matchingReview.fullStaffCount} staff at 100%`} />
          <MetricCard label="0% Staff" value={matchingReview.zeroUtilizationStaffCount} />
          <MetricCard label="Recommendations" value={assignmentRecommendations.length} description={`${assignments.length} finalized assignments`} />
          <MetricCard label="要確認" value={matchingReview.reviewIssueCount} description="unassigned / tough / utilization" />
        </div>
        <div className="matching-chart-grid">
          <div>
            <h3>Status Summary</h3>
            <MatchingStatusChart
              assigned={matchingReview.assignedCount}
              toughAssigned={matchingReview.toughAssignedCount}
              unassigned={matchingReview.unassignedCount}
            />
          </div>
          <div>
            <h3>Staff稼働分布</h3>
            <UtilizationChart rows={matchingReview.staffUtilizationBars} />
          </div>
        </div>
        <div className="matching-issue-grid">
          <ReviewList title="未割当Role" emptyMessage="未割当はありません。" rows={matchingReview.unassignedRoles} />
          <ReviewList title="育成枠" emptyMessage="育成枠はありません。" rows={matchingReview.toughAssignedRoles} />
          <ReviewList title="高稼働Staff" emptyMessage="100%到達Staffはありません。" rows={matchingReview.highUtilizationStaff} />
          <ReviewList title="0% Staff" emptyMessage="0% Staffはありません。" rows={matchingReview.zeroUtilizationStaff} />
        </div>
      </section>

      <section className="panel">
        <h2>PJ別Matching結果</h2>
        <div className="matching-project-workspace">
          <div className="matching-project-grid">
          {matchingReview.projects.slice(0, 12).map((project) => (
            <button
              className={`matching-project-card ${project.unassignedCount > 0 ? "needs-review" : ""} ${selectedProject?.code === project.code ? "selected" : ""}`}
              key={project.code}
              type="button"
              onClick={() => setSelectedProjectCode(project.code)}
            >
              <div className="matching-project-head">
                <div>
                  <span>{project.code}</span>
                  <strong>{project.theme || "Theme TBD"}</strong>
                  <small>{project.account || "Account TBD"}</small>
                </div>
                <StatusBadge status={project.unassignedCount > 0 ? "draft" : "approved"} />
              </div>
              <div className="project-interest-meta">
                <span>{project.assignedCount} assigned</span>
                <span>{project.toughAssignedCount} tough</span>
                <span>{project.unassignedCount} unassigned</span>
              </div>
            </button>
          ))}
          </div>

          <aside className={`matching-project-detail ${selectedProject?.unassignedCount ? "needs-review" : ""}`}>
            {selectedProject ? (
              <>
                <div className="matching-project-head">
                  <div>
                    <span>{selectedProject.code}</span>
                    <strong>{selectedProject.theme || "Theme TBD"}</strong>
                    <small>{selectedProject.account || "Account TBD"}</small>
                  </div>
                  <StatusBadge status={selectedProject.unassignedCount > 0 ? "draft" : "approved"} />
                </div>
                <div className="project-interest-meta">
                  <span>{selectedProject.assignedCount} assigned</span>
                  <span>{selectedProject.toughAssignedCount} tough</span>
                  <span>{selectedProject.unassignedCount} unassigned</span>
                </div>
                <ul className="matching-project-role-list">
                  {selectedProject.roles.map((role) => (
                  <li
                    className={role.status === "assigned" ? "assigned" : "unassigned"}
                    key={`${selectedProject.code}:${role.requestCode}:${role.slot}:${role.staffCode}:${role.status}`}
                  >
                    <div>
                      <span>{role.roleLabel}</span>
                      <strong>{role.staffLabel || "未割当"}</strong>
                      <small>slot {role.slot} / {role.assignmentType || role.reason || "n/a"}</small>
                    </div>
                    <div className="assignee-controls">
                      <select
                        aria-label={`${role.requestCode}-${role.slot}のAssignee`}
                        value={role.staffCode}
                        onChange={(event) => updateAssignee(role.requestCode, role.slot, event.target.value)}
                      >
                        <option value="">未割当</option>
                        {staffs.map((staff) => (
                          <option key={String(staff.code)} value={String(staff.code)}>
                            {String(staff.name ?? staff.code)}
                          </option>
                        ))}
                      </select>
                      <div className="assignment-toggle" aria-label={`${role.requestCode}-${role.slot}の割当種別`}>
                        {["standard", "training"].map((type) => (
                          <button
                            className={role.assignmentType === type ? "selected" : "secondary"}
                            disabled={!role.staffCode}
                            key={type}
                            type="button"
                            onClick={() => updateAssignmentType(role.requestCode, role.slot, type)}
                          >
                            {type === "standard" ? "通常" : "育成"}
                          </button>
                        ))}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
              </>
            ) : (
              <p className="muted">Matching対象のPJがありません。</p>
            )}
          </aside>
        </div>
      </section>

      <section className="panel">
        <h2>Raw Matching Detail</h2>
        <p className="muted">生データは通常表示せず、原因調査が必要な場合だけ開きます。</p>
        <RawDataDisclosure
          title="Matching traceを確認"
          rows={trace.slice(0, 100)}
          columns={[
            { key: "opportunity_request_code", label: "Request" },
            { key: "role_code", label: "Role" },
            { key: "staff_code", label: "Staff" },
            { key: "assignment_type", label: "Type" },
            { key: "status", label: "Status" },
            { key: "skill_gap", label: "Gap" },
          ]}
        />
      </section>
    </div>
  );
}

type MatchingRoleRow = {
  requestCode: string;
  slot: number;
  roleCode: string;
  roleLabel: string;
  staffCode: string;
  staffLabel: string;
  assignmentType: string;
  status: string;
  reason: string;
};

type MatchingProjectRow = {
  code: string;
  theme: string;
  account: string;
  assignedCount: number;
  toughAssignedCount: number;
  unassignedCount: number;
  roles: MatchingRoleRow[];
};

type ReviewItem = {
  label: string;
  value: string;
  description?: string;
};

function ReviewList({
  title,
  rows,
  emptyMessage,
}: {
  title: string;
  rows: ReviewItem[];
  emptyMessage: string;
}) {
  return (
    <article className="matching-review-list">
      <h3>{title}</h3>
      {rows.length === 0 ? <p className="muted">{emptyMessage}</p> : null}
      <ul>
        {rows.slice(0, 8).map((row) => (
          <li key={`${row.label}:${row.value}`}>
            <span>{row.label}</span>
            <strong>{row.value}</strong>
            {row.description ? <small>{row.description}</small> : null}
          </li>
        ))}
      </ul>
    </article>
  );
}

function buildMatchingReview({
  trace,
  requests,
  opportunities,
  staffs,
  utilization,
  assignmentRecommendations,
  rolesByCode,
  staffsByCode,
}: {
  trace: Row[];
  requests: Row[];
  opportunities: Row[];
  staffs: Row[];
  utilization: Row[];
  assignmentRecommendations: Row[];
  rolesByCode: Map<string, Row>;
  staffsByCode: Map<string, Row>;
}) {
  const requestByCode = byCode(requests);
  const opportunityByCode = byCode(opportunities);
  const recommendationBySlot = new Map<string, Row>();
  for (const recommendation of assignmentRecommendations) {
    const key = `${String(recommendation.opportunity_request_code ?? "")}:${numberValue(recommendation.slot)}`;
    recommendationBySlot.set(key, recommendation);
  }
  const reviewedTrace = trace.map((row) => {
    const requestCode = String(row.opportunity_request_code ?? "");
    const slot = numberValue(row.slot);
    const recommendation = recommendationBySlot.get(`${requestCode}:${slot}`);
    if (!recommendation) {
      return row;
    }
    return {
      ...row,
      staff_code: recommendation.staff_code,
      assignment_type: recommendation.assignment_type,
      status: "assigned",
      reason: String(recommendation.matching_reason ?? row.reason ?? ""),
    };
  });
  const utilizationByStaff = new Map<string, number[]>();
  for (const row of utilization) {
    const staffCode = String(row.staff_code ?? "");
    utilizationByStaff.set(staffCode, [
      ...(utilizationByStaff.get(staffCode) ?? []),
      numberValue(row.utilization_percentage),
    ]);
  }
  const assignedTrace = reviewedTrace.filter((row) => String(row.status) === "assigned");
  const unassignedTrace = reviewedTrace.filter((row) => String(row.status) !== "assigned");
  const toughAssignedTrace = assignedTrace.filter((row) => String(row.assignment_type) === "training");
  const staffAverageUtilization = staffs.map((staff) => {
    const staffCode = String(staff.code ?? "");
    const values = utilizationByStaff.get(staffCode) ?? [];
    const average = values.length ? values.reduce((total, value) => total + value, 0) / values.length : 0;
    const max = values.length ? Math.max(...values) : 0;
    return {
      staffCode,
      name: String(staff.name ?? staffCode),
      average,
      max,
    };
  });
  const projects = buildProjectRows(reviewedTrace, requestByCode, opportunityByCode, rolesByCode, staffsByCode);
  const unassignedRoles = summarizeTraceByRole(unassignedTrace, "reason", rolesByCode);
  const toughAssignedRoles = summarizeTraceByRole(toughAssignedTrace, "skill_gap", rolesByCode);
  const highUtilizationStaff = staffAverageUtilization
    .filter((staff) => staff.max >= 100)
    .sort((a, b) => b.max - a.max)
    .map((staff) => ({
      label: staff.name,
      value: `${formatNumber(staff.max)}% max`,
      description: staff.staffCode,
    }));
  const zeroUtilizationStaff = staffAverageUtilization
    .filter((staff) => staff.max === 0)
    .map((staff) => ({
      label: staff.name,
      value: "0%",
      description: staff.staffCode,
    }));
  return {
    assignedCount: assignedTrace.length,
    toughAssignedCount: toughAssignedTrace.length,
    unassignedCount: unassignedTrace.length,
    averageUtilization: Math.round(
      staffAverageUtilization.reduce((total, staff) => total + staff.average, 0) / Math.max(staffAverageUtilization.length, 1),
    ),
    fullStaffCount: highUtilizationStaff.length,
    zeroUtilizationStaffCount: zeroUtilizationStaff.length,
    reviewIssueCount: unassignedTrace.length + toughAssignedTrace.length + highUtilizationStaff.length + zeroUtilizationStaff.length,
    unassignedRoles,
    toughAssignedRoles,
    highUtilizationStaff,
    zeroUtilizationStaff,
    projects,
    staffUtilizationBars: staffAverageUtilization
      .sort((a, b) => b.average - a.average)
      .map((staff) => ({
        label: staff.name,
        value: Math.round(staff.average),
        description: staff.staffCode,
      })),
    recommendationCount: assignmentRecommendations.length,
  };
}

function MatchingStatusChart({
  assigned,
  toughAssigned,
  unassigned,
}: {
  assigned: number;
  toughAssigned: number;
  unassigned: number;
}) {
  const standardAssigned = Math.max(0, assigned - toughAssigned);
  const data: ChartData<"doughnut"> = {
    labels: ["通常割当", "育成枠", "未割当"],
    datasets: [
      {
        data: [standardAssigned, toughAssigned, unassigned],
        backgroundColor: ["#006AB6", "#66A9C9", "#D18B00"],
        borderWidth: 0,
      },
    ],
  };
  const options: ChartOptions<"doughnut"> = {
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "bottom",
      },
    },
  };
  return (
    <div className="matching-chart-frame">
      <Doughnut data={data} options={options} />
    </div>
  );
}

function UtilizationChart({
  rows,
}: {
  rows: { label: string; value: number; description?: string }[];
}) {
  const topRows = rows.slice(0, 12);
  const data: ChartData<"bar"> = {
    labels: topRows.map((row) => row.label),
    datasets: [
      {
        label: "平均稼働率",
        data: topRows.map((row) => row.value),
        backgroundColor: topRows.map((row) => row.value >= 90 ? "#D18B00" : "#006AB6"),
        borderRadius: 4,
      },
    ],
  };
  const options: ChartOptions<"bar"> = {
    indexAxis: "y",
    maintainAspectRatio: false,
    scales: {
      x: {
        min: 0,
        max: 100,
        ticks: {
          callback: (value) => `${value}%`,
        },
      },
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.parsed.x}%`,
        },
      },
    },
  };
  return (
    <div className="matching-chart-frame wide">
      <Bar data={data} options={options} />
    </div>
  );
}

function buildProjectRows(
  trace: Row[],
  requestByCode: Map<string, Row>,
  opportunityByCode: Map<string, Row>,
  rolesByCode: Map<string, Row>,
  staffsByCode: Map<string, Row>,
): MatchingProjectRow[] {
  const grouped = new Map<string, MatchingProjectRow>();
  for (const row of trace) {
    const requestCode = String(row.opportunity_request_code ?? "");
    const request = requestByCode.get(requestCode) ?? {};
    const opportunityCode = String(request.opportunity_code ?? "unknown");
    const opportunity = opportunityByCode.get(opportunityCode) ?? {};
    const current = grouped.get(opportunityCode) ?? {
      code: opportunityCode,
      theme: String(opportunity.theme ?? ""),
      account: String(opportunity.account_code ?? ""),
      assignedCount: 0,
      toughAssignedCount: 0,
      unassignedCount: 0,
      roles: [],
    };
    const status = String(row.status ?? "");
    const assignmentType = String(row.assignment_type ?? "");
    if (status === "assigned") {
      current.assignedCount += 1;
    } else {
      current.unassignedCount += 1;
    }
    if (assignmentType === "training") {
      current.toughAssignedCount += 1;
    }
    const roleCode = String(row.role_code ?? request.role_code ?? "");
    const staffCode = String(row.staff_code ?? "");
    current.roles.push({
      requestCode,
      slot: numberValue(row.slot),
      roleCode,
      roleLabel: labelFromMap(rolesByCode, roleCode),
      staffCode,
      staffLabel: labelFromMap(staffsByCode, staffCode),
      assignmentType,
      status,
      reason: String(row.reason ?? ""),
    });
    grouped.set(opportunityCode, current);
  }
  return Array.from(grouped.values()).sort(
    (a, b) => b.unassignedCount - a.unassignedCount || b.toughAssignedCount - a.toughAssignedCount || a.code.localeCompare(b.code),
  );
}

function summarizeTraceByRole(
  items: Row[],
  detailKey: string,
  rolesByCode: Map<string, Row>,
): ReviewItem[] {
  const grouped = new Map<string, { count: number; details: Set<string> }>();
  for (const item of items) {
    const roleCode = String(item.role_code ?? "unknown");
    const current = grouped.get(roleCode) ?? { count: 0, details: new Set<string>() };
    current.count += 1;
    const detail = String(item[detailKey] ?? "");
    if (detail) {
      current.details.add(detail);
    }
    grouped.set(roleCode, current);
  }
  return Array.from(grouped.entries())
    .map(([roleCode, value]) => ({
      label: labelFromMap(rolesByCode, roleCode),
      value: `${value.count} slots`,
      description: Array.from(value.details).slice(0, 2).join(", "),
    }))
    .sort((a, b) => Number.parseInt(b.value, 10) - Number.parseInt(a.value, 10));
}
