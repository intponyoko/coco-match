import StatusBadge from "./StatusBadge";
import type { ApprovalRecord } from "../lib/approvalState";
import type { AppData } from "../lib/data";
import { workflowNodesFromAppData } from "../lib/workflowState";

type RingiWorkflowMapProps = {
  data: AppData | null;
  records: ApprovalRecord[];
};

export default function RingiWorkflowMap({ data, records }: RingiWorkflowMapProps) {
  const nodes = workflowNodesFromAppData(data, records);
  const firstBlocked = nodes.find((node) => !node.isComplete);

  return (
    <section className="panel">
      <h2>稟議Workflow</h2>
      <p className="muted">
        現在止まっている工程:{" "}
        <strong>
          {firstBlocked ? `${firstBlocked.step}. ${firstBlocked.title}` : "全工程完了"}
        </strong>
      </p>
      <div className="workflow-map">
        {(["経営層", "部署層", "個人層"] as const).map((role) => (
          <div className="workflow-lane" key={role}>
            <div className="workflow-lane-label">{role}</div>
            {nodes
              .filter((node) => node.role === role)
              .map((node) => (
                <a
                  className={`workflow-node ${firstBlocked?.title === node.title ? "current" : ""}`}
                  href={node.pagePath}
                  key={node.title}
                >
                  <div className="workflow-node-title">
                    {node.step}. {node.title}
                  </div>
                  <div className="muted">{node.ownerDescription}</div>
                  <StatusBadge status={node.status} />
                  <div className="muted">
                    {node.isComplete ? "完了" : "対応待ち"} / {node.count.toLocaleString()} 件 / {node.tableNames.join(", ")}
                  </div>
                </a>
              ))}
          </div>
        ))}
      </div>
    </section>
  );
}
