import type { AgentInsightResponse } from "../lib/apiClient";

type AICopilotPanelProps = {
  response: AgentInsightResponse | null;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
};

export default function AICopilotPanel({
  response,
  loading = false,
  error = null,
  onRefresh,
}: AICopilotPanelProps) {
  const rationale = response?.rationale ?? [];
  const watchouts = response?.watchouts ?? [];
  const alternatives = response?.alternatives ?? [];
  const suggestedActions = response?.suggested_actions ?? [];
  const impact = response?.impact ?? [];
  const evidenceRefs = response?.evidence_refs ?? [];
  const evidenceCards = evidenceRefs.slice(0, 4).map((item) => ({
    key: item.evidence_id,
    title: conciseText(item.title, "Evidence"),
    summary: conciseText(item.summary, "根拠の要約はありません。"),
    source: evidenceSourceLabel(item.source),
    kind: evidenceKindLabel(item.metadata),
  }));
  const sectionTitles = titlesForStage(String(response?.stage ?? ""));
  const loadingCards = loading && !response;
  const showConfidenceBadge = response?.confidence_score !== undefined || response?.confidence_label === "high" || response?.confidence_label === "medium";

  return (
    <section className="ai-copilot-panel">
      <div className="ai-copilot-head">
        <div>
          <h2>{response?.headline ?? "AI Copilot"}</h2>
          <p className="muted">
            {response?.summary ?? "選択中の候補に対する提案理由・懸念・代替案を手動で確認できます。"}
          </p>
        </div>
        <div className="ai-copilot-badges">
          {showConfidenceBadge ? (
            <span className={`ai-copilot-badge ${badgeClass(response?.confidence_label)}`}>
              {confidenceLabel(response?.confidence_label)}
              {response?.confidence_score !== undefined ? ` ${Math.round(Number(response.confidence_score) * 100)}%` : ""}
            </span>
          ) : null}
          {onRefresh ? (
            <button className="secondary" type="button" onClick={onRefresh} disabled={loading}>
              AI Review
            </button>
          ) : null}
        </div>
      </div>

      {loading ? <p className="muted">AIが最新の判断根拠を再計算しています...</p> : null}
      {error ? <p role="alert" className="error-text">{error}</p> : null}

      <div className="ai-copilot-impact-strip">
        {impact.length === 0 ? <span className="muted">Impactを集計中です。</span> : null}
        {impact.slice(0, 4).map((item, index) => (
          <article className="ai-impact-card" key={`${String(item.label ?? item.title ?? "impact")}:${index}`}>
            <span>{String(item.label ?? item.title ?? "Impact")}</span>
            <strong>{String(item.value ?? item.body ?? "-")}</strong>
          </article>
        ))}
      </div>

      <div className="ai-copilot-grid">
        <InsightColumn
          title={sectionTitles.rationale}
          empty="根拠を準備中です。"
          items={rationale.slice(0, 2)}
          loading={loadingCards}
        />
        <InsightColumn
          title={sectionTitles.watchouts}
          empty="いまは大きな懸念は見えていません。"
          items={watchouts.slice(0, 2)}
          loading={loadingCards}
        />
        <InsightColumn
          title={sectionTitles.alternatives}
          empty="代替案はまだありません。"
          items={alternatives.slice(0, 2)}
          loading={loadingCards}
        />
      </div>

      <div className="ai-copilot-footer">
        <div>
          <strong>Suggested next moves</strong>
          <div className="ai-chip-row">
            {suggestedActions.length === 0 ? <span className="muted">アクション候補はありません。</span> : null}
            {suggestedActions.slice(0, 2).map((item, index) => (
              <span className="ai-chip" key={`${String(item.label ?? "action")}:${index}`}>
                {conciseText(item.label ?? item.title, "Action")}
              </span>
            ))}
          </div>
        </div>
        <div>
          <div className="ai-evidence-head">
            <strong>Evidence</strong>
            <span className="ai-mini-badge neutral">{evidenceRefs.length}件</span>
          </div>
          <div className="ai-evidence-list">
            {loadingCards ? <EvidenceSkeleton /> : null}
            {!loadingCards && evidenceCards.length === 0 ? <span className="muted">Evidenceはまだありません。</span> : null}
            {evidenceCards.map((item) => (
              <article className="ai-evidence-card" key={item.key}>
                <div className="ai-evidence-card-head">
                  <strong>{item.title}</strong>
                  <span className="ai-mini-badge neutral">{item.kind}</span>
                </div>
                <p>{item.summary}</p>
                <span className="ai-evidence-source">{item.source}</span>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function evidenceSourceLabel(source?: string) {
  if (!source) {
    return "Source: n/a";
  }
  if (source === "offline") {
    return "Source: offline";
  }
  return `Source: ${source}`;
}

function evidenceKindLabel(metadata?: Record<string, unknown>) {
  const origin = String(metadata?.origin ?? metadata?.node_type ?? metadata?.kind ?? "");
  if (origin === "offline_mock") {
    return "offline";
  }
  if (origin) {
    return origin;
  }
  return "evidence";
}

function InsightColumn({
  title,
  items,
  empty,
  loading,
}: {
  title: string;
  items: { title?: string; body?: string; severity?: string; tag?: string }[];
  empty: string;
  loading?: boolean;
}) {
  return (
    <section className="ai-insight-column">
      <h3>{title}</h3>
      {loading ? <ColumnSkeleton /> : null}
      {items.length === 0 ? <p className="muted">{empty}</p> : null}
      <ul>
        {items.slice(0, 4).map((item, index) => (
          <li key={`${String(item.title ?? "item")}:${index}`}>
            <div className="ai-insight-row">
              <strong>{conciseText(item.title, "Insight")}</strong>
              {item.severity ? <span className={`ai-mini-badge ${badgeClass(item.severity)}`}>{String(item.severity)}</span> : null}
              {!item.severity && item.tag ? <span className="ai-mini-badge neutral">{String(item.tag)}</span> : null}
            </div>
            <span>{conciseText(item.body, "")}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ColumnSkeleton() {
  return (
    <div className="ai-loading-stack" aria-hidden="true">
      <span className="ai-loading-line short" />
      <span className="ai-loading-line" />
    </div>
  );
}

function EvidenceSkeleton() {
  return (
    <>
      <article className="ai-evidence-card loading" aria-hidden="true">
        <div className="ai-loading-stack">
          <span className="ai-loading-line short" />
          <span className="ai-loading-line" />
        </div>
      </article>
      <article className="ai-evidence-card loading" aria-hidden="true">
        <div className="ai-loading-stack">
          <span className="ai-loading-line short" />
          <span className="ai-loading-line" />
        </div>
      </article>
    </>
  );
}

function badgeClass(value: string | undefined) {
  if (value === "high") {
    return "success";
  }
  if (value === "medium") {
    return "info";
  }
  if (value === "critical") {
    return "danger";
  }
  if (value === "review") {
    return "warning";
  }
  return "neutral";
}

function confidenceLabel(value: string | undefined) {
  if (value === "high") {
    return "AI confidence: high";
  }
  if (value === "medium") {
    return "AI confidence: medium";
  }
  return "AI review";
}

function conciseText(value: unknown, fallback: string) {
  if (value == null || value === "") {
    return fallback;
  }
  const text = typeof value === "string" ? value : stringifyBrief(value);
  return stripNoise(text).trim() || fallback;
}

function stringifyBrief(value: unknown) {
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .slice(0, 3)
      .map(([key, item]) => `${key}: ${String(item)}`);
    return entries.join(" / ");
  }
  return String(value);
}

function stripNoise(value: string) {
  return value.replace(/【[^】]+†source】/g, "").replace(/\s+/g, " ");
}

function titlesForStage(stage: string) {
  switch (stage) {
    case "sales_plan":
      return {
        rationale: "Portfolio signals",
        watchouts: "Planning risks",
        alternatives: "Portfolio options",
      };
    case "theme_solution":
      return {
        rationale: "Theme signals",
        watchouts: "Theme risks",
        alternatives: "Nearby options",
      };
    case "project_request":
      return {
        rationale: "Project sizing",
        watchouts: "Delivery risks",
        alternatives: "Staffing options",
      };
    case "project_interest":
      return {
        rationale: "Career fit",
        watchouts: "Monthly tradeoffs",
        alternatives: "Other paths",
      };
    case "matching":
      return {
        rationale: "Assignment fit",
        watchouts: "Coverage risks",
        alternatives: "Fallback assignments",
      };
    default:
      return {
        rationale: "Why AI likes this",
        watchouts: "Watchouts",
        alternatives: "Alternatives",
      };
  }
}
