import { useEffect, useMemo, useState } from "react";
import CareerPlanningPanel, { type CareerSuggestion } from "../../components/CareerPlanningPanel";
import DataTable from "../../components/DataTable";
import HITLStageHeader from "../../components/HITLStageHeader";
import MetricCard from "../../components/MetricCard";
import StatusBadge from "../../components/StatusBadge";
import SubmissionProgress from "../../components/SubmissionProgress";
import { runAgentEndpoint, type AgentResponse } from "../../lib/apiClient";
import { useApprovalState } from "../../lib/approvalState";
import { byCode, numberValue, rows, useAppData, type Row } from "../../lib/data";
import { formatNumber } from "../../lib/formatting";
import { rowByCode, uniqueCount } from "../../lib/rowUtils";
import { saveSessionTable, sessionRows } from "../../lib/tableSession";
import { approveTable, runAgentWorkflowEndpoint, tablesFromAppData } from "../../lib/workflowRunner";

type MonthChoice = {
  type: "project" | "training" | "open";
  value: string;
};

const interestOptions = [
  ["high", "強く参画したい"],
  ["medium", "参画したい"],
  ["low", "条件次第"],
  ["not_interested", "参画しない"],
];

const assignmentTypeLabel: Record<string, string> = {
  standard: "通常枠",
  training: "育成枠",
};

const eligibilityLabel: Record<string, string> = {
  eligible: "要件充足",
  training_eligible: "育成対象",
};

export default function ProjectInterestScreen() {
  const { data, loading, error } = useAppData();
  const approval = useApprovalState();
  const staffs = rows(data, "sample", "staffs");
  const titles = byCode(rows(data, "sample", "titles"));
  const roles = rows(data, "sample", "roles");
  const roleByCode = byCode(roles);
  const periods = rows(data, "sample", "fiscal_periods").filter((period) =>
    String(period.code ?? "").startsWith("2026-"),
  );
  const opportunities = sessionRows(data, "planning", "opportunities");
  const opportunityRequests = sessionRows(data, "planning", "opportunity_requests");
  const opportunityByCode = byCode(opportunities);
  const preferenceOptions = sessionRows(data, "planning", "staff_preference_options");
  const submittedPlans = sessionRows(data, "planning", "staff_preference_submissions");
  const [staffCode, setStaffCode] = useState(String(staffs[0]?.code ?? ""));
  const [comment, setComment] = useState("");
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [careerPlanResponse, setCareerPlanResponse] = useState<AgentResponse | null>(null);
  const [careerPlanLoading, setCareerPlanLoading] = useState(false);
  const [careerPlanError, setCareerPlanError] = useState<string | null>(null);
  const [interestByOpportunity, setInterestByOpportunity] = useState<Record<string, string>>({});
  const [monthChoices, setMonthChoices] = useState<Record<string, MonthChoice>>({});
  const [selectedPeriodCode, setSelectedPeriodCode] = useState("");
  const staff = staffs.find((row) => String(row.code) === staffCode);
  const optionsForStaff = useMemo(
    () =>
      preferenceOptions
        .filter((option) => String(option.staff_code ?? "") === staffCode)
        .sort(optionSort),
    [preferenceOptions, staffCode],
  );

  useEffect(() => {
    if (!staffCode && staffs.length > 0) {
      setStaffCode(String(staffs[0]?.code ?? ""));
    }
  }, [staffCode, staffs]);

  useEffect(() => {
    if (!selectedPeriodCode && periods.length > 0) {
      setSelectedPeriodCode(String(periods[0]?.code ?? ""));
    }
  }, [periods, selectedPeriodCode]);

  useEffect(() => {
    setCareerPlanResponse(null);
    setCareerPlanError(null);
  }, [comment, staffCode]);

  const optionsByMonth = useMemo(() => {
    const map = new Map<string, Row[]>();
    for (const period of periods) {
      map.set(String(period.code), []);
    }
    for (const option of optionsForStaff) {
      const periodCode = String(option.period_code ?? "");
      if (!map.has(periodCode)) {
        continue;
      }
      map.get(periodCode)?.push(option);
    }
    for (const [periodCode, monthOptions] of map.entries()) {
      map.set(periodCode, monthOptions.sort(optionSort));
    }
    return map;
  }, [optionsForStaff, periods]);
  const demandSlotsByMonth = useMemo(() => {
    const map = new Map<string, number>();
    for (const period of periods) {
      const periodCode = String(period.code);
      const monthOptions = optionsByMonth.get(periodCode) ?? [];
      map.set(periodCode, sumDistinctBy(monthOptions, "opportunity_request_code", "request_total_slots"));
    }
    return map;
  }, [optionsByMonth, periods]);
  const totalOpenRequestSlots = useMemo(
    () => opportunityRequests.reduce(
      (total, request) => total + numberValue(request.headcount) + numberValue(request.training_slots),
      0,
    ),
    [opportunityRequests],
  );
  const eligibleDemandSlots = useMemo(
    () => sumDistinctBy(optionsForStaff, "opportunity_request_code", "request_total_slots"),
    [optionsForStaff],
  );

  const opportunitySummaries = useMemo(() => {
    const grouped = new Map<string, Row[]>();
    for (const option of optionsForStaff) {
      const opportunityCode = String(option.opportunity_code ?? "");
      grouped.set(opportunityCode, [...(grouped.get(opportunityCode) ?? []), option]);
    }
    return Array.from(grouped.entries()).map(([opportunityCode, options]) => {
      const opportunity = opportunityByCode.get(opportunityCode) ?? {};
      const rolesText = Array.from(
        new Set(
          options.map((option) =>
            String(roleByCode.get(String(option.role_code ?? ""))?.name ?? option.role_code ?? ""),
          ),
        ),
      ).join(", ");
      return {
        code: opportunityCode,
        theme: String(opportunity.theme ?? options[0]?.theme ?? ""),
        roles: rolesText,
        months: new Set(options.map((option) => String(option.period_code ?? ""))).size,
        demand_slots: sumDistinctBy(options, "opportunity_request_code", "request_total_slots"),
        standard_options: options.filter((option) => String(option.assignment_type) === "standard").length,
        training_options: options.filter((option) => String(option.assignment_type) === "training").length,
        interest: interestByOpportunity[opportunityCode] ?? "medium",
        status: approval.statusOf("staff_preference_options", "draft"),
      };
    }) as Row[];
  }, [approval, interestByOpportunity, opportunityByCode, optionsForStaff, roleByCode]);
  const categorizedSuggestions = useMemo(
    () => categorizeCareerSuggestions(opportunitySummaries, optionsForStaff),
    [opportunitySummaries, optionsForStaff],
  );

  const selectedProjectCount = Object.values(monthChoices).filter((choice) => choice.type === "project").length;
  const selectedTrainingCount = Object.values(monthChoices).filter((choice) => choice.type === "training").length;
  const activeMonths = periods.filter((period) => {
    const periodCode = String(period.code);
    return (optionsByMonth.get(periodCode)?.length ?? 0) > 0;
  }).length;
  const selectedAllocations = Object.values(monthChoices)
    .filter((choice) => choice.type === "project")
    .map((choice) => rowByCode(optionsForStaff, choice.value, "preference_option_code"))
    .filter((option): option is Row => Boolean(option));
  const plannedMonthlyAllocation = selectedAllocations.reduce(
    (total, option) => total + numberValue(option.allocation_percentage),
    0,
  );
  const submissionPreview = useMemo(
    () =>
      buildSubmissionRows({
        staffCode,
        periods,
        monthChoices,
        optionsForStaff,
        interestByOpportunity,
        comment,
      }),
    [comment, interestByOpportunity, monthChoices, optionsForStaff, periods, staffCode],
  );
  const selectedMonthOptions = optionsByMonth.get(selectedPeriodCode) ?? [];
  const selectedMonthChoice = monthChoices[selectedPeriodCode] ?? { type: "open", value: "" };
  const selectedMonthOption =
    selectedMonthChoice.type === "project"
    ? rowByCode(optionsForStaff, selectedMonthChoice.value, "preference_option_code")
    : undefined;
  if (loading) return <p>Loading app data...</p>;
  if (error) return <p role="alert">Data load error: {error}</p>;

  function setInterest(opportunityCode: string, interest: string) {
    setInterestByOpportunity((current) => ({ ...current, [opportunityCode]: interest }));
  }

  function setMonthProject(periodCode: string, preferenceOptionCode: string) {
    setMonthChoices((current) => ({
      ...current,
      [periodCode]: preferenceOptionCode
        ? { type: "project", value: preferenceOptionCode }
        : { type: "open", value: "" },
    }));
  }

  function setMonthTraining(periodCode: string, roleCode: string) {
    setMonthChoices((current) => ({
      ...current,
      [periodCode]: roleCode ? { type: "training", value: roleCode } : { type: "open", value: "" },
    }));
  }

  function chooseRecommended(periodCode: string) {
    const recommended = optionsByMonth.get(periodCode)?.[0];
    if (recommended) {
      setMonthProject(periodCode, String(recommended.preference_option_code ?? ""));
    }
  }

  function chooseAllRecommended() {
    setMonthChoices((current) => {
      const next = { ...current };
      for (const period of periods) {
        const periodCode = String(period.code ?? "");
        const recommended = optionsByMonth.get(periodCode)?.[0];
        if (recommended) {
          next[periodCode] = {
            type: "project",
            value: String(recommended.preference_option_code ?? ""),
          };
        }
      }
      return next;
    });
  }

  async function submitYearPlan() {
    const selectedOptionCodes = new Set(
      Object.values(monthChoices)
        .filter((choice) => choice.type === "project")
        .map((choice) => choice.value),
    );
    const updatedPreferenceOptions = preferenceOptions.map((option) => {
      const optionStaffCode = String(option.staff_code ?? "");
      const opportunityCode = String(option.opportunity_code ?? "");
      const optionCode = String(option.preference_option_code ?? "");
      if (optionStaffCode !== staffCode) {
        return {
          ...option,
          preference_status: String(option.preference_status ?? "") === "not_selected"
            ? "medium"
            : option.preference_status,
          comment: String(option.comment ?? "") || "Demo default submission.",
        };
      }
      return {
        ...option,
        preference_status: selectedOptionCodes.has(optionCode)
          ? "selected"
          : (interestByOpportunity[opportunityCode] ?? String(option.preference_status ?? "not_selected")),
        comment,
      };
    });
    const defaultSubmittedRows = buildDefaultSubmissionRows({
      staffs,
      periods,
      currentStaffCode: staffCode,
      comment: "Demo default submission.",
    });
    const submittedRows = [
      ...submittedPlans.filter((row) => !staffs.some((staff) => String(staff.code) === String(row.staff_code))),
      ...defaultSubmittedRows,
      ...submissionPreview,
    ];
    saveSessionTable(data, "staff_preference_options", updatedPreferenceOptions);
    saveSessionTable(data, "staff_preference_submissions", submittedRows);
    setRunning(true);
    setRunError(null);
    try {
      await runAgentWorkflowEndpoint(
        "/agent/matching/review",
        {
          ...tablesFromAppData(data),
          staff_preference_options: updatedPreferenceOptions,
          staff_preference_submissions: submittedRows,
        },
        approveTable({}, "staff_preference_options", "individual", comment),
      );
      approval.setTableApproval(
        "staff_preference_options",
        "submitted",
        "individual",
        JSON.stringify({ comment, interestByOpportunity, monthChoices, demoDefaultSubmittedStaffs: staffs.length - 1 }),
      );
      approval.setTableApproval(
        "staff_preference_submissions",
        "submitted",
        "individual",
        `${comment} / Demo default submitted ${Math.max(0, staffs.length - 1)} other staff.`,
      );
      window.location.href = "/";
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  async function requestCareerPlan() {
    setCareerPlanLoading(true);
    setCareerPlanError(null);
    try {
      const response = await runAgentEndpoint("/agent/career-plan/propose", {
        tables: {
          ...tablesFromAppData(data),
          staffs: staffs.filter((row) => String(row.code ?? "") === staffCode),
          staff_preference_options: optionsForStaff,
        },
        metadata: {
          current_staff_code: staffCode,
          current_staff_name: String(staff?.name ?? ""),
          career_goal: comment,
        },
      });
      setCareerPlanResponse(response);
    } catch (err) {
      setCareerPlanError(err instanceof Error ? err.message : String(err));
    } finally {
      setCareerPlanLoading(false);
    }
  }

  return (
    <div className="grid">
      <HITLStageHeader
        owner="個人層"
        canEdit={["月ごとのPJ参画希望", "PJに入らない月のRole別研修希望", "一年のキャリアコメント"]}
        canView={["自分が参加できるPJ期間", "PJごとのRole構成", "通常枠/育成枠の候補理由"]}
        workflow={{
          step: 4,
          status: approval.statusOf("staff_preference_submissions", "pending"),
          prerequisite: "Opportunity / OpportunityRequestがMaterializeされ、月別PJ候補が生成されていること",
          nextAction: "個人希望を反映してMatching案を生成",
        }}
      />
      <section className="panel year-plan-control-panel">
        <div className="project-interest-header">
          <div className="toolbar compact">
            <label className="field">
              Staff
              <select value={staffCode} onChange={(event) => setStaffCode(event.target.value)}>
                {staffs.map((row) => (
                  <option key={String(row.code)} value={String(row.code)}>
                    {String(row.name)} / {String(titles.get(String(row.title_code))?.name ?? row.title_code)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </section>

      <div className="grid cols-3">
        <MetricCard
          label="Selected Staff"
          value={String(staff?.name ?? "N/A")}
          description={String(titles.get(String(staff?.title_code ?? ""))?.name ?? staff?.title_code ?? "")}
        />
        <MetricCard label="PJ候補" value={opportunitySummaries.length} description={`${formatNumber(optionsForStaff.length)} eligible option rows`} />
        <MetricCard label="Open Demand Slots" value={totalOpenRequestSlots} description={`${eligibleDemandSlots} slots visible to selected staff`} />
        <MetricCard label="候補がある月" value={`${activeMonths} / ${periods.length}`} description="selected staff only" />
        <MetricCard label="PJ希望月" value={selectedProjectCount} />
        <MetricCard label="研修希望月" value={selectedTrainingCount} />
        <MetricCard label="選択済み稼働率合計" value={`${formatNumber(plannedMonthlyAllocation)}%`} description="月選択の単純合計" />
      </div>

      <CareerPlanningPanel
        loading={careerPlanLoading}
        error={careerPlanError}
        response={careerPlanResponse}
        suggestions={categorizedSuggestions}
        goal={comment}
        onGoalChange={setComment}
        onRequest={requestCareerPlan}
      />

      <section className="panel year-plan-editor">
        <div className="year-plan-editor-head">
          <div>
          <h2>一年の月次計画</h2>
          <p className="muted">
            月を選択し、その月に入りたいPJ、研修、または空き月を決めます。
            通常枠はRole要件を満たす候補、育成枠はSkill gapとPJ内mentor条件を満たす候補です。
          </p>
          </div>
          <button className="secondary" disabled={optionsForStaff.length === 0} onClick={chooseAllRecommended}>
            推奨を一括入力
          </button>
        </div>
        {optionsForStaff.length === 0 ? (
          <p className="muted">まだPJ候補がありません。Opportunity/RequestのMaterialize後に候補が表示されます。</p>
        ) : null}
        <div className="year-plan-workspace">
          <div className="year-calendar-grid" aria-label="年間カレンダー">
            {periods.map((period) => {
              const periodCode = String(period.code);
              const monthOptions = optionsByMonth.get(periodCode) ?? [];
              const choice = monthChoices[periodCode] ?? { type: "open", value: "" };
              const selectedOption = choice.type === "project" ? rowByCode(optionsForStaff, choice.value, "preference_option_code") : undefined;
              const trainingRole = choice.type === "training" ? roleByCode.get(choice.value) : undefined;
              return (
                <button
                  className={`month-summary-card ${selectedPeriodCode === periodCode ? "selected" : ""}`}
                  key={periodCode}
                  type="button"
                  onClick={() => setSelectedPeriodCode(periodCode)}
                >
                  <span>{periodCode.slice(5, 7)}月</span>
                  <strong>{monthChoiceTitle(choice, selectedOption, trainingRole)}</strong>
                  <small>{uniqueCount(monthOptions, "opportunity_code")} PJ / {demandSlotsByMonth.get(periodCode) ?? 0} demand slots</small>
                  <StatusBadge status={choice.type === "open" ? "draft" : "submitted"} />
                </button>
              );
            })}
          </div>

          <aside className="month-detail-panel">
            <div className="month-detail-head">
              <div>
                <h3>{selectedPeriodCode || "Month"}</h3>
                <p className="muted">
                  {uniqueCount(selectedMonthOptions, "opportunity_code")} PJ / {selectedMonthOptions.length} eligible options / {demandSlotsByMonth.get(selectedPeriodCode) ?? 0} demand slots
                </p>
              </div>
              <StatusBadge status={selectedMonthChoice.type === "open" ? "draft" : "submitted"} />
            </div>

            <div className="month-choice-actions">
              <button className="secondary" disabled={selectedMonthOptions.length === 0} onClick={() => chooseRecommended(selectedPeriodCode)}>
                推奨PJを選ぶ
              </button>
              <button className="secondary" onClick={() => setMonthProject(selectedPeriodCode, "")}>空き月にする</button>
            </div>

            <label className="field">
              PJ候補
              <select
                aria-label={`${selectedPeriodCode}のPJ希望`}
                value={selectedMonthChoice.type === "project" ? selectedMonthChoice.value : ""}
                onChange={(event) => setMonthProject(selectedPeriodCode, event.target.value)}
              >
                <option value="">PJを選択しない</option>
                {selectedMonthOptions.slice(0, 80).map((option) => (
                  <option key={String(option.preference_option_code)} value={String(option.preference_option_code)}>
                    {optionLabel(option, roleByCode)}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              PJに入らない場合の研修
              <select
                aria-label={`${selectedPeriodCode}の研修希望`}
                value={selectedMonthChoice.type === "training" ? selectedMonthChoice.value : ""}
                onChange={(event) => setMonthTraining(selectedPeriodCode, event.target.value)}
              >
                <option value="">研修を選択しない</option>
                {roles.map((role) => (
                  <option key={String(role.code)} value={String(role.code)}>
                    {String(role.name)}
                  </option>
                ))}
              </select>
            </label>

            {selectedMonthOption ? (
              <article className="selected-month-project">
                <span>{String(selectedMonthOption.opportunity_code)}</span>
                <strong>{String(roleByCode.get(String(selectedMonthOption.role_code ?? ""))?.name ?? selectedMonthOption.role_code)}</strong>
                <p>
                  {assignmentTypeLabel[String(selectedMonthOption.assignment_type)] ?? String(selectedMonthOption.assignment_type)}
                  {" / "}
                  {eligibilityLabel[String(selectedMonthOption.eligibility_status)] ?? String(selectedMonthOption.eligibility_status)}
                  {" / "}
                  {String(selectedMonthOption.allocation_percentage)}%
                </p>
                <small>{String(selectedMonthOption.reason ?? "")}</small>
              </article>
            ) : (
              <p className="muted">この月はPJ未選択です。PJに入らない場合は研修Roleを選べます。</p>
            )}
          </aside>
        </div>
      </section>

      <section className="panel">
        <h2>PJ別の参画意思</h2>
        <p className="muted">月別選択とは別に、PJ全体への関心をMatchingスコアへ反映します。</p>
        <div className="project-interest-card-grid">
          {opportunitySummaries.slice(0, 12).map((opportunity) => (
            <article className="project-interest-card" key={String(opportunity.code)}>
              <span>{String(opportunity.code)}</span>
              <strong>{String(opportunity.theme || "Theme TBD")}</strong>
              <small>{String(opportunity.roles || "Role TBD")}</small>
              <div className="project-interest-meta">
                <span>{String(opportunity.months)} months</span>
                <span>{String(opportunity.demand_slots ?? 0)} demand slots</span>
                <span>{String(opportunity.standard_options)} standard</span>
                <span>{String(opportunity.training_options)} training</span>
              </div>
              <label className="field">
                参画意思
              <select
                value={interestByOpportunity[String(opportunity.code)] ?? "medium"}
                onChange={(event) => setInterest(String(opportunity.code), event.target.value)}
              >
                {interestOptions.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              </label>
            </article>
          ))}
        </div>
      </section>

      <details className="panel raw-data-details">
        <summary>提出予定Tableを確認</summary>
        <DataTable
          rows={submissionPreview.slice(0, 24)}
          columns={[
            { key: "staff_code", label: "Staff" },
            { key: "period_code", label: "Month" },
            { key: "choice_type", label: "Choice" },
            { key: "opportunity_code", label: "Opportunity" },
            { key: "role_code", label: "Role", format: (value) => String(roleByCode.get(String(value ?? ""))?.name ?? value ?? "") },
            { key: "assignment_type", label: "Type" },
            { key: "allocation_percentage", label: "Allocation" },
            { key: "preference_status", label: "Preference" },
            { key: "comment", label: "Comment" },
          ]}
          emptyMessage="月別計画を選択すると提出予定Tableが表示されます。"
        />
      </details>

      <section className="panel year-plan-submit-panel">
        <div>
          <h2>Matching案の作成</h2>
          <p className="muted">
            月別計画と参画意思をまとめて提出し、Matching案を再計算します。
          </p>
        </div>
        {runError ? <p role="alert" className="error-text">{runError}</p> : null}
        {running ? (
          <SubmissionProgress
            title="Proposing Matching"
            body="提出された年間計画を集約し、個人希望を反映したMatching案を再計算しています。"
          />
        ) : null}
        <button className="primary" disabled={running || optionsForStaff.length === 0} onClick={submitYearPlan}>
          年間計画を提出してMatching案を作成
        </button>
      </section>
    </div>
  );
}

function optionLabel(option: Row, roleByCode: Map<string, Row>): string {
  const role = roleByCode.get(String(option.role_code ?? ""));
  return `${String(option.opportunity_code)} / ${String(role?.name ?? option.role_code)} / ${assignmentTypeLabel[String(option.assignment_type)] ?? String(option.assignment_type)} / ${String(option.allocation_percentage)}%`;
}

function monthChoiceTitle(choice: MonthChoice, option: Row | undefined, trainingRole: Row | undefined): string {
  if (choice.type === "project" && option) {
    return String(option.opportunity_code ?? "PJ");
  }
  if (choice.type === "training") {
    return `研修: ${String(trainingRole?.name ?? choice.value)}`;
  }
  return "未選択";
}

function optionSort(a: Row, b: Row): number {
  const typeRank = (value: Row) => String(value.assignment_type) === "standard" ? 0 : 1;
  return (
    typeRank(a) - typeRank(b)
    || numberValue(b.score) - numberValue(a.score)
    || numberValue(a.skill_gap) - numberValue(b.skill_gap)
    || numberValue(a.allocation_percentage) - numberValue(b.allocation_percentage)
    || String(a.opportunity_code ?? "").localeCompare(String(b.opportunity_code ?? ""))
  );
}

function buildSubmissionRows({
  staffCode,
  periods,
  monthChoices,
  optionsForStaff,
  interestByOpportunity,
  comment,
}: {
  staffCode: string;
  periods: Row[];
  monthChoices: Record<string, MonthChoice>;
  optionsForStaff: Row[];
  interestByOpportunity: Record<string, string>;
  comment: string;
}): Row[] {
  return periods.map((period, index) => {
    const periodCode = String(period.code ?? "");
    const choice = monthChoices[periodCode] ?? { type: "open", value: "" };
    const option = choice.type === "project" ? rowByCode(optionsForStaff, choice.value, "preference_option_code") : undefined;
    const opportunityCode = String(option?.opportunity_code ?? "");
    return {
      submission_code: `SUB-${staffCode}-${periodCode}-${index + 1}`,
      staff_code: staffCode,
      period_code: periodCode,
      choice_type: choice.type,
      preference_option_code: choice.type === "project" ? choice.value : "",
      training_role_code: choice.type === "training" ? choice.value : "",
      opportunity_code: opportunityCode,
      opportunity_request_code: String(option?.opportunity_request_code ?? ""),
      role_code: String(option?.role_code ?? choice.value ?? ""),
      assignment_type: String(option?.assignment_type ?? ""),
      allocation_percentage: numberValue(option?.allocation_percentage),
      preference_status: opportunityCode ? (interestByOpportunity[opportunityCode] ?? "medium") : "not_selected",
      comment,
      submitted_at: new Date().toISOString(),
    };
  });
}

function buildDefaultSubmissionRows({
  staffs,
  periods,
  currentStaffCode,
  comment,
}: {
  staffs: Row[];
  periods: Row[];
  currentStaffCode: string;
  comment: string;
}): Row[] {
  return staffs
    .filter((staff) => String(staff.code ?? "") !== currentStaffCode)
    .flatMap((staff) =>
      periods.map((period, index) => {
        const staffCode = String(staff.code ?? "");
        const periodCode = String(period.code ?? "");
        return {
          submission_code: `SUB-${staffCode}-${periodCode}-${index + 1}`,
          staff_code: staffCode,
          period_code: periodCode,
          choice_type: "open",
          preference_option_code: "",
          training_role_code: "",
          opportunity_code: "",
          opportunity_request_code: "",
          role_code: "",
          assignment_type: "",
          allocation_percentage: 0,
          preference_status: "medium",
          comment,
          submitted_at: new Date().toISOString(),
        };
      }),
    );
}

function sumDistinctBy(rows: Row[], keyField: string, valueField: string): number {
  const distinct = new Map<string, Row>();
  for (const row of rows) {
    const key = String(row[keyField] ?? "");
    if (!key || distinct.has(key)) {
      continue;
    }
    distinct.set(key, row);
  }
  return Array.from(distinct.values()).reduce(
    (total, row) => total + numberValue(row[valueField]),
    0,
  );
}

function categorizeCareerSuggestions(
  opportunitySummaries: Row[],
  optionsForStaff: Row[],
): CareerSuggestion[] {
  const optionsByOpportunity = new Map<string, Row[]>();
  for (const option of optionsForStaff) {
    const opportunityCode = String(option.opportunity_code ?? "");
    optionsByOpportunity.set(opportunityCode, [...(optionsByOpportunity.get(opportunityCode) ?? []), option]);
  }
  return opportunitySummaries
    .map((summary) => {
      const opportunityCode = String(summary.code ?? "");
      const rows = optionsByOpportunity.get(opportunityCode) ?? [];
      const standardRows = rows.filter((row) => String(row.assignment_type ?? "") === "standard");
      const minGap = rows.reduce((min, row) => Math.min(min, numberValue(row.skill_gap)), Number.POSITIVE_INFINITY);
      const category: CareerSuggestion["category"] = standardRows.length > 0 && minGap <= 1
        ? "ready_now"
        : standardRows.length > 0
          ? "stretch"
          : "training_first";
      const topOption = [...rows].sort(optionSort)[0];
      return {
        code: opportunityCode,
        theme: String(summary.theme ?? ""),
        roles: String(summary.roles ?? ""),
        reason: suggestionReason(category, topOption, summary),
        category,
        demandSlots: numberValue(summary.demand_slots),
        standardOptions: numberValue(summary.standard_options),
        trainingOptions: numberValue(summary.training_options),
      };
    })
    .sort((left, right) => {
      const rank = (value: { category: string }) =>
        value.category === "ready_now" ? 0 : value.category === "stretch" ? 1 : 2;
      return rank(left) - rank(right) || left.code.localeCompare(right.code);
    });
}

function suggestionReason(
  category: "ready_now" | "stretch" | "training_first",
  option: Row | undefined,
  summary: Row,
) {
  const base = String(option?.reason ?? "").trim();
  if (base) {
    return base;
  }
  if (category === "ready_now") {
    return `今のスキルで ${String(summary.roles ?? "対象Role")} に入りやすい候補です。`;
  }
  if (category === "stretch") {
    return `少し背伸びになりますが、${String(summary.roles ?? "対象Role")} を試しやすい候補です。`;
  }
  return `育成枠や研修と組み合わせると ${String(summary.roles ?? "対象Role")} を試しやすい候補です。`;
}
