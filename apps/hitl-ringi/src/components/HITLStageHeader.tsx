import StatusBadge from "./StatusBadge";
import type { ApprovalStatus } from "../lib/approvalState";
import { workflowDefinitions } from "../lib/workflowState";
import type { RoleAccessPanelProps } from "./RoleAccessPanel";

type HITLStageHeaderProps = RoleAccessPanelProps & {
  workflow?: {
    step: number;
    status: ApprovalStatus | string;
    nextAction: string;
    prerequisite?: string;
    tableNames?: string[];
  };
};

export default function HITLStageHeader({
  owner,
  canEdit,
  canView,
  workflow,
}: HITLStageHeaderProps) {
  const definition = workflow
    ? workflowDefinitions().find((node) => node.step === workflow.step)
    : undefined;
  const tables = workflow?.tableNames ?? definition?.tableNames ?? [];

  return (
    <section className="hitl-stage-header" aria-label="画面の担当と稟議工程">
      <div className="hitl-stage-main">
        <div className="workflow-context-eyebrow">
          {workflow ? `Step ${workflow.step}` : "MVP"}
        </div>
        <h2>{definition?.title ?? "Pipeline Debug"}</h2>
        <p className="muted">
          主担当: {owner}
          {definition?.ownerDescription ? ` / ${definition.ownerDescription}` : ""}
        </p>
      </div>
      <div className="workflow-context-grid">
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
        {workflow ? (
          <>
            <div>
              <strong>前提</strong>
              <p>{workflow.prerequisite ?? "前工程が完了していること"}</p>
            </div>
            <div>
              <strong>承認後に実行</strong>
              <p>{workflow.nextAction}</p>
            </div>
            <div>
              <strong>対象Table</strong>
              <p>{tables.join(", ") || "N/A"}</p>
            </div>
          </>
        ) : null}
      </div>
      {workflow ? <StatusBadge status={workflow.status} /> : null}
    </section>
  );
}
