export type AccessOwner = "経営層" | "部署層" | "個人層" | "全員" | "管理";

export type RoleAccessPanelProps = {
  owner: AccessOwner;
  canEdit: string[];
  canView: string[];
};

export default function RoleAccessPanel({ owner, canEdit, canView }: RoleAccessPanelProps) {
  return (
    <section className="access-panel" aria-label="画面の利用者と権限">
      <div>
        <div className="access-owner">主担当: {owner}</div>
        <div className="muted">この画面でできることを明示しています。</div>
      </div>
      <div>
        <strong>編集・承認</strong>
        <ul>
          {canEdit.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div>
        <strong>参照</strong>
        <ul>
          {canView.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
