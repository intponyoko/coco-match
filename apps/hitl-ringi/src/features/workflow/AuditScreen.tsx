import ApprovalTimeline from "../../components/ApprovalTimeline";
import DataTable from "../../components/DataTable";
import RoleAccessPanel from "../../components/RoleAccessPanel";
import { useApprovalState } from "../../lib/approvalState";
import { clearSessionTables, readSessionTables } from "../../lib/data";

export default function AuditScreen() {
  const approval = useApprovalState();
  const sessionTables = readSessionTables();
  const sessionTableCount = Object.keys(sessionTables).length;
  const sessionRowCount = Object.values(sessionTables).reduce(
    (total, table) => total + table.length,
    0,
  );
  const rows = approval.records.map((record) => ({
    ...record,
    updatedAtLocal: new Date(record.updatedAt).toLocaleString("ja-JP"),
  }));

  function resetDemoState() {
    clearSessionTables();
    approval.clearApprovals();
    window.location.href = "/";
  }

  return (
    <div className="grid">
      <RoleAccessPanel
        owner="管理"
        canEdit={["Demo用Pipeline実行結果のリセット", "localStorage上の検証用承認履歴の削除"]}
        canView={["承認・コメント履歴", "browser sessionに残っているPipeline実行結果"]}
      />
      <section className="panel">
        <h2>Demo Reset</h2>
        <p className="muted">
          Pipeline実行結果と承認履歴を消し、SalesPlanだけが投入された初期状態に戻します。
        </p>
        <div className="toolbar">
          <button className="danger" onClick={resetDemoState}>Reset demo pipeline state</button>
          <span className="muted">
            session tables: {sessionTableCount.toLocaleString()} / rows: {sessionRowCount.toLocaleString()}
          </span>
        </div>
      </section>
      <section className="panel">
        <h2>Local Approval Log</h2>
        <div className="toolbar">
          <button className="danger" onClick={approval.clearApprovals}>Clear local approval state</button>
        </div>
        <DataTable rows={rows} columns={[{ key: "tableName", label: "Table" }, { key: "status", label: "Status" }, { key: "actorRole", label: "Actor" }, { key: "comment", label: "Comment" }, { key: "updatedAtLocal", label: "Updated" }]} />
      </section>
      <section className="panel">
        <h2>Timeline</h2>
        <ApprovalTimeline records={approval.records} />
      </section>
    </div>
  );
}
