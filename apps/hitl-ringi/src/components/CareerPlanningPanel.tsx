import { useEffect, useState } from "react";
import type { AgentResponse } from "../lib/apiClient";

export type CareerSuggestion = {
  code: string;
  theme: string;
  roles: string;
  reason: string;
  category: "ready_now" | "stretch" | "training_first";
  demandSlots: number;
  standardOptions: number;
  trainingOptions: number;
};

type CareerPlanningPanelProps = {
  loading: boolean;
  error: string | null;
  response: AgentResponse | null;
  suggestions: CareerSuggestion[];
  goal: string;
  onGoalChange: (value: string) => void;
  onRequest: () => void;
};

const categoryLabels: Record<CareerSuggestion["category"], string> = {
  ready_now: "今すぐ挑戦",
  stretch: "少し背伸び",
  training_first: "研修付きで挑戦",
};

const categoryDescriptions: Record<CareerSuggestion["category"], string> = {
  ready_now: "今のスキルで入りやすい候補です。",
  stretch: "少し難しいが挑戦価値のある候補です。",
  training_first: "研修や育成枠から入ると良い候補です。",
};

export default function CareerPlanningPanel({
  loading,
  error,
  response,
  suggestions,
  goal,
  onGoalChange,
  onRequest,
}: CareerPlanningPanelProps) {
  const [collapsed, setCollapsed] = useState(true);
  const explanations = response?.explanations ?? [];
  const summary = explanations.find((item) => String(item.kind ?? "") === "summary");
  const keyMessage = String(
    summary?.reason
    ?? "希望入力と候補PJをもとに、今すぐ挑戦できる機会と背伸び候補を整理します。",
  );
  const hasResult = loading || Boolean(error) || Boolean(response);
  const grouped = {
    ready_now: suggestions.filter((item) => item.category === "ready_now").slice(0, 3),
    stretch: suggestions.filter((item) => item.category === "stretch").slice(0, 3),
    training_first: suggestions.filter((item) => item.category === "training_first").slice(0, 3),
  };

  useEffect(() => {
    if (loading || response || error) {
      setCollapsed(false);
    }
  }, [error, loading, response]);

  return (
    <section className="panel career-planning-panel">
      <div className="career-planning-head">
        <div>
          <h2>Career Planning AI</h2>
          <p className="muted">
            興味や今年の方針をもとに、試しやすいPJと育成導線を整理します。
          </p>
        </div>
        <button
          type="button"
          className="secondary"
          onClick={() => setCollapsed((current) => !current)}
          aria-expanded={!collapsed}
        >
          {collapsed ? "ひらく" : "たたむ"}
        </button>
      </div>
      {collapsed ? (
        hasResult ? (
          <div className="career-planning-keymsg">
            <strong>Key Message</strong>
            <p>{keyMessage}</p>
          </div>
        ) : (
          <p className="muted">キャリア方針を書いて相談すると、挑戦しやすいPJ候補を整理します。</p>
        )
      ) : (
        <>
          <div className="career-planning-controls">
            <label className="field wide">
              今年のキャリア方針
              <input
                value={goal}
                onChange={(event) => onGoalChange(event.target.value)}
                placeholder="例: データ設計や要件整理を少し広げたい"
              />
            </label>
            <button type="button" className="secondary" onClick={onRequest} disabled={loading}>
              {loading ? "整理中..." : "Career Planning AIに相談"}
            </button>
          </div>
          {error ? <p role="alert" className="error-text">{error}</p> : null}
          {hasResult ? (
            <>
              <div className="career-planning-summary">
                <strong>Key Message</strong>
                <p>{keyMessage}</p>
              </div>
              <div className="career-planning-grid">
                {(["ready_now", "stretch", "training_first"] as const).map((category) => (
                  <section className="career-category" key={category}>
                    <div className="career-category-head">
                      <strong>{categoryLabels[category]}</strong>
                      <span>{categoryDescriptions[category]}</span>
                    </div>
                    {grouped[category].length === 0 ? (
                      <p className="muted">該当候補はまだありません。</p>
                    ) : null}
                    {grouped[category].map((item) => (
                      <article className="career-suggestion-card" key={`${category}:${item.code}`}>
                        <span>{item.code}</span>
                        <strong>{item.theme || "Theme TBD"}</strong>
                        <small>{item.roles || "Role TBD"}</small>
                        <p>{item.reason}</p>
                        <div className="career-suggestion-meta">
                          <span>{item.demandSlots} demand slots</span>
                          <span>{item.standardOptions} standard</span>
                          <span>{item.trainingOptions} training</span>
                        </div>
                      </article>
                    ))}
                  </section>
                ))}
              </div>
            </>
          ) : null}
        </>
      )}
    </section>
  );
}
