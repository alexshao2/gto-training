import React, { useEffect, useState } from "react";
import type { CoachFeedback } from "../types/api";

interface Props {
  feedback: CoachFeedback | null;
  enabled: boolean;
}

const SEV_COLORS: Record<string, string> = {
  ok: "#10b981",
  minor: "#f59e0b",
  major: "#f97316",
  blunder: "#ef4444",
};

const SEV_ICONS: Record<string, string> = {
  ok: "✓",
  minor: "!",
  major: "!!",
  blunder: "✕",
};

export const CoachPanel: React.FC<Props> = ({ feedback, enabled }) => {
  const [expanded, setExpanded] = useState(false);
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    if (feedback) {
      setPulse(true);
      const t = setTimeout(() => setPulse(false), 600);
      return () => clearTimeout(t);
    }
  }, [feedback]);

  if (!enabled) {
    return (
      <div className="coach-panel coach-panel-off">
        <span className="coach-icon">○</span>
        <span>Coach đang tắt</span>
      </div>
    );
  }

  if (!feedback) {
    return (
      <div className="coach-panel coach-panel-idle">
        <span className="coach-icon">◎</span>
        <span>HLV đang chờ — hãy thực hiện hành động.</span>
      </div>
    );
  }

  const color = SEV_COLORS[feedback.severity] ?? "#10b981";
  const icon = SEV_ICONS[feedback.severity] ?? "•";
  const m = (feedback.metrics ?? {}) as Record<string, unknown>;

  return (
    <div
      className={
        "coach-panel coach-panel-" +
        feedback.severity +
        (pulse ? " coach-pulse" : "")
      }
      style={{ borderColor: color }}
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="coach-row">
        <span className="coach-icon" style={{ color }}>
          {icon}
        </span>
        <strong className="coach-headline">{feedback.headline}</strong>
        <span className="coach-toggle">{expanded ? "▾" : "▸"}</span>
      </div>
      {expanded && (
        <>
          <p className="coach-detail">{feedback.detail}</p>
          {feedback.correct_action && (
            <div className="coach-correct">
              GTO line:&nbsp;
              <span className="coach-action">{feedback.correct_action}</span>
              {feedback.correct_size_bb != null && (
                <span> @ ~{feedback.correct_size_bb}bb</span>
              )}
            </div>
          )}
          {Object.keys(m).length > 0 && (
            <div className="coach-metrics">
              {"equity_vs_random" in m && (
                <span className="metric">
                  Equity: <b>{((m.equity_vs_random as number) * 100).toFixed(0)}%</b>
                </span>
              )}
              {"pot_odds" in m && (
                <span className="metric">
                  Pot odds: <b>{((m.pot_odds as number) * 100).toFixed(0)}%</b>
                </span>
              )}
              {"spr" in m && m.spr !== null && (
                <span className="metric">
                  SPR: <b>{m.spr as number}</b>
                </span>
              )}
              {"category" in m && (
                <span className="metric">
                  Hand: <b>{m.category as string}</b>
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};
