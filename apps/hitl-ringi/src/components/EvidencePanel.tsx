import DataTable from "./DataTable";
import type { Row } from "../lib/data";

type EvidencePanelProps = {
  evidenceCaseIds: string;
  nodes: Row[];
  edges: Row[];
  retrievedEvidenceRows?: Row[];
};

export default function EvidencePanel({
  evidenceCaseIds,
  nodes,
  edges,
  retrievedEvidenceRows = [],
}: EvidencePanelProps) {
  const ids = evidenceCaseIds
    .split(";")
    .map((id) => id.trim())
    .filter(Boolean);
  const retrievalRows = retrievedEvidenceRows.filter((row) => {
    const evidenceId = canonicalCaseId(String(row.evidence_id ?? ""));
    return ids.includes(evidenceId);
  });
  const canonicalIds = Array.from(
    new Set([
      ...ids.map(canonicalCaseId),
      ...retrievalRows.map((row) => canonicalCaseId(String(row.evidence_id ?? ""))),
    ].filter(Boolean)),
  );
  const caseNodeIds = canonicalIds.flatMap((id) => [id, `case:${id}`]);
  const caseNodes = nodes.filter((node) => {
    const nodeId = String(node.node_id ?? "");
    const nodeSource = String(node.source ?? "");
    return caseNodeIds.includes(nodeId)
      || (String(node.node_type ?? "") === "past_case" && canonicalIds.includes(nodeSource));
  });
  const relatedEdges = edges.filter(
    (edge) =>
      caseNodeIds.includes(String(edge.source_id ?? ""))
      || caseNodeIds.includes(String(edge.target_id ?? ""))
      || canonicalIds.includes(String(edge.source ?? "")),
  );
  const adjacentNodeIds = new Set(
    relatedEdges.flatMap((edge) => [String(edge.source_id ?? ""), String(edge.target_id ?? "")]),
  );
  const relatedNodes = nodes.filter(
    (node) =>
      adjacentNodeIds.has(String(node.node_id ?? ""))
      || caseNodeIds.includes(String(node.node_id ?? ""))
      || canonicalIds.includes(String(node.source ?? "")),
  );

  return (
    <section className="evidence-panel">
      <div className="toolbar compact">
        <div>
          <h3>Evidence</h3>
          <p className="muted">case id: {canonicalIds.join(", ") || "N/A"}</p>
        </div>
      </div>
      {caseNodes.length ? (
        <>
          <div className="evidence-summary-list">
            {caseNodes.slice(0, 3).map((caseNode) => (
              <div className="evidence-summary-row" key={String(caseNode.node_id)}>
                <strong>{String(caseNode.label ?? caseNode.node_id)}</strong>
                <span>{String(caseNode.source ?? "")}</span>
              </div>
            ))}
          </div>
          <details className="raw-disclosure">
            <summary>Evidence detailsを開く</summary>
            <div className="evidence-case-list">
              {caseNodes.map((caseNode) => (
                <article className="evidence-case-card" key={String(caseNode.node_id)}>
                  <div className="portfolio-card-meta">{String(caseNode.source ?? "")}</div>
                  <h3>{String(caseNode.label ?? caseNode.node_id)}</h3>
                  <EvidenceNodeList
                    title="Solution / Account"
                    nodes={connectedNodes(caseNode, relatedEdges, relatedNodes, ["solution", "account"])}
                  />
                  <EvidenceNodeList
                    title="Theme / Pain"
                    nodes={connectedNodes(caseNode, relatedEdges, relatedNodes, ["theme", "customer_pain"])}
                  />
                  <EvidenceNodeList
                    title="Required Roles"
                    nodes={connectedNodes(caseNode, relatedEdges, relatedNodes, ["role"])}
                  />
                </article>
              ))}
            </div>
          </details>
        </>
      ) : retrievalRows.length ? (
        <>
          <div className="evidence-summary-list">
            {retrievalRows.slice(0, 3).map((row, index) => (
              <div className="evidence-summary-row" key={`${String(row.evidence_id ?? "retrieval")}:${index}`}>
                <strong>{String(row.title ?? row.evidence_id ?? "Retrieved evidence")}</strong>
                <span>{String(row.source ?? "") || "retrieved evidence"}</span>
              </div>
            ))}
          </div>
          <details className="raw-disclosure">
            <summary>Retrieved evidenceを開く</summary>
            <div className="evidence-case-list">
              {retrievalRows.map((row, index) => (
                <article className="evidence-case-card" key={`${String(row.evidence_id ?? "retrieval")}:${index}`}>
                  <div className="portfolio-card-meta">{String(row.source ?? "") || "retrieved evidence"}</div>
                  <h3>{String(row.title ?? row.evidence_id ?? "Retrieved evidence")}</h3>
                  <p>{String(row.snippet ?? "") || "詳細なsnippetはありません。"}</p>
                </article>
              ))}
            </div>
          </details>
        </>
      ) : (
        <p className="muted">Knowledge Graphに該当caseの詳細がまだありません。</p>
      )}
      <details className="raw-disclosure">
        <summary>Evidence nodes / edgesを確認</summary>
        <h3>Nodes</h3>
        <DataTable rows={relatedNodes} columns={[{ key: "node_id", label: "Node" }, { key: "node_type", label: "Type" }, { key: "label", label: "Label" }]} />
        <h3>Edges</h3>
        <DataTable rows={relatedEdges} columns={[{ key: "source_id", label: "Source" }, { key: "target_id", label: "Target" }, { key: "edge_type", label: "Type" }, { key: "weight", label: "Weight" }]} />
      </details>
    </section>
  );
}

function canonicalCaseId(value: string): string {
  if (!value) {
    return "";
  }
  const trimmed = value.trim();
  if (trimmed.startsWith("case:")) {
    return trimmed.slice(5);
  }
  return trimmed.split(":")[0] ?? trimmed;
}

function connectedNodes(
  caseNode: Row,
  edges: Row[],
  nodes: Row[],
  nodeTypes: string[],
) {
  const caseNodeId = String(caseNode.node_id ?? "");
  const connectedIds = new Set(
    edges
      .filter(
        (edge) =>
          String(edge.source_id ?? "") === caseNodeId ||
          String(edge.target_id ?? "") === caseNodeId,
      )
      .flatMap((edge) => [String(edge.source_id ?? ""), String(edge.target_id ?? "")]),
  );
  connectedIds.delete(caseNodeId);
  return nodes.filter(
    (node) =>
      connectedIds.has(String(node.node_id ?? "")) &&
      nodeTypes.includes(String(node.node_type ?? "")),
  );
}

function EvidenceNodeList({ title, nodes }: { title: string; nodes: Row[] }) {
  if (nodes.length === 0) {
    return null;
  }
  return (
    <div>
      <strong>{title}</strong>
      <ul className="evidence-node-list">
        {nodes.map((node) => (
          <li key={String(node.node_id)}>{String(node.label ?? node.node_id)}</li>
        ))}
      </ul>
    </div>
  );
}
