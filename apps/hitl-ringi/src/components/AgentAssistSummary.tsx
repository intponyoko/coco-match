import type { AgentResponse } from "../lib/apiClient";

type AgentAssistSummaryProps = {
  response: AgentResponse | null;
};

export default function AgentAssistSummary({ response }: AgentAssistSummaryProps) {
  if (!response) {
    return null;
  }
  const explanations = response.explanations ?? [];
  const diagnostics = response.diagnostics ?? [];
  const evidenceRefs = response.evidence_refs ?? [];
  return (
    <section className="agent-assist-summary">
      <div>
        <h3>AI支援の根拠</h3>
        <p className="muted">
          {String(response.metadata?.agent ?? "agent")} / {String(response.metadata?.agent_mode ?? "fallback")}
        </p>
      </div>
      <div className="agent-summary-grid">
        <div>
          <strong>説明</strong>
          {explanations.length === 0 ? <p className="muted">説明はありません。</p> : null}
          <ul>
            {explanations.slice(0, 4).map((item, index) => (
              <li key={`${String(item.row_code ?? item.title ?? "explanation")}:${index}`}>
                {String(item.title ?? item.table ?? "提案")}:
                {" "}
                <span>{String(item.reason ?? "")}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <strong>診断</strong>
          {diagnostics.length === 0 ? <p className="muted">診断はありません。</p> : null}
          <ul>
            {diagnostics.slice(0, 4).map((item, index) => (
              <li key={`${String(item.kind ?? "diagnostic")}:${index}`}>
                {String(item.kind ?? "diagnostic")}:
                {" "}
                <span>{diagnosticText(item)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <strong>Evidence</strong>
          {evidenceRefs.length === 0 ? <p className="muted">参照Evidenceはありません。</p> : null}
          <ul>
            {evidenceRefs.slice(0, 4).map((item) => (
              <li key={item.evidence_id}>
                {item.evidence_id}: <span>{item.title}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function diagnosticText(item: Record<string, unknown>) {
  if ("table" in item && "rows" in item) {
    return `${String(item.table)} ${String(item.rows)} rows`;
  }
  if ("counts" in item) {
    return JSON.stringify(item.counts);
  }
  if ("average" in item) {
    return `avg ${Number(item.average).toFixed(1)}`;
  }
  return JSON.stringify(item);
}

