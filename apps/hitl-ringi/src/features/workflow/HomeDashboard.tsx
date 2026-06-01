import DataTable from "../../components/DataTable";
import MetricCard from "../../components/MetricCard";
import RingiWorkflowMap from "../../components/RingiWorkflowMap";
import RoleAccessPanel from "../../components/RoleAccessPanel";
import { useApprovalState } from "../../lib/approvalState";
import { useAppData } from "../../lib/data";
import { managementSummary } from "../../lib/derivedMetrics";
import { downloadAssignmentPlan } from "../../lib/downloads";
import { formatCurrency, formatPercent } from "../../lib/formatting";
import { workflowNodesFromAppData } from "../../lib/workflowState";

export default function HomeDashboard() {
  const { data, loading, error } = useAppData();
  const approval = useApprovalState();
  const summary = managementSummary(data);

  if (loading) return <p>Loading app data...</p>;
  if (error) return <p role="alert">Data load error: {error}</p>;

  const inboxRows = workflowNodesFromAppData(data, approval.records)
    .filter((node) => !node.isComplete)
    .map((node) => ({
      step: node.step,
      role: node.role,
      task: node.title,
      owner: node.ownerDescription,
      status: node.status,
      tables: node.tableNames.join(", "),
      count: node.count,
    }));

  return (
    <div className="grid">
      <RoleAccessPanel
        owner="全員"
        canEdit={["自分の担当工程の編集・承認・コメント"]}
        canView={["全体の稟議停止箇所", "現在の予想Matching率", "最近の承認履歴"]}
      />
      <RingiWorkflowMap data={data} records={approval.records} />
      <div className="grid cols-3">
        <MetricCard label="Plan Revenue" value={formatCurrency(summary.planRevenue)} />
        <MetricCard label="Opportunity Revenue" value={formatCurrency(summary.opportunityRevenue)} />
        <MetricCard label="Expected Matching Rate" value={formatPercent(summary.matchingRate)} />
      </div>
      <section className="panel">
        <h2>Assignment Plan</h2>
        <p className="muted">
          最終確定されたAssignment planをCSVでダウンロードします。
        </p>
        <button
          type="button"
          onClick={() => downloadAssignmentPlan(data)}
          disabled={(data?.planning?.opportunity_assignments?.length ?? 0) === 0}
        >
          Download Assignment Plan
        </button>
      </section>
      <section className="panel">
        <h2>Inbox</h2>
        <p className="muted">現在承認されていない工程だけを表示します。履歴はAuditで確認します。</p>
        <DataTable
          rows={inboxRows}
          columns={[
            { key: "step", label: "Step" },
            { key: "role", label: "Role" },
            { key: "task", label: "Task" },
            { key: "owner", label: "Owner Responsibility" },
            { key: "status", label: "Status" },
            { key: "tables", label: "Tables" },
            { key: "count", label: "Rows" },
          ]}
          emptyMessage="No pending workflow tasks."
        />
      </section>
    </div>
  );
}
