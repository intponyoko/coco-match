type StatusBadgeProps = {
  status: string;
};

const statusLabels: Record<string, string> = {
  draft: "下書き",
  edited: "編集中",
  submitted: "提出済み",
  pending: "待機中",
  approved: "承認済み",
  assigned: "アサイン済み",
  unassigned: "未アサイン",
  tough_assigned: "育成アサイン",
};

const statusTone: Record<string, string> = {
  approved: "success",
  assigned: "success",
  pending: "warning",
  edited: "warning",
  submitted: "info",
  unassigned: "danger",
  tough_assigned: "info",
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const tone = statusTone[status] ?? "default";
  return <span className={`status-badge ${tone}`}>{statusLabels[status] ?? status}</span>;
}
