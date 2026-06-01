import StatusBadge from "./StatusBadge";
import type { ApprovalRecord } from "../lib/approvalState";

type ApprovalTimelineProps = {
  records: ApprovalRecord[];
};

export default function ApprovalTimeline({ records }: ApprovalTimelineProps) {
  if (records.length === 0) {
    return <p className="muted">No approval actions yet.</p>;
  }

  return (
    <ol className="timeline">
      {records
        .slice()
        .reverse()
        .map((record) => (
          <li key={`${record.tableName}-${record.updatedAt}`}>
            <div>
              <strong>{record.tableName}</strong>
            </div>
            <StatusBadge status={record.status} />
            <div className="muted">
              {record.actorRole} / {new Date(record.updatedAt).toLocaleString("ja-JP")}
            </div>
            {record.comment ? <p>{record.comment}</p> : null}
          </li>
        ))}
    </ol>
  );
}
