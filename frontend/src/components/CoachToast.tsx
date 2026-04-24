import React, { useEffect, useState } from "react";
import type { CoachFeedback } from "../types/api";

interface Props {
  feedback: CoachFeedback | null | undefined;
  visible: boolean;
  onClose: () => void;
}

const SEV_ICON: Record<string, string> = {
  blunder: "✗",
  major: "⚠",
  minor: "⚡",
  ok: "✓",
};

const SEV_LABEL_VI: Record<string, string> = {
  blunder: "BLUNDER",
  major: "SAI LẦM LỚN",
  minor: "LEAK NHỎ",
  ok: "ĐÚNG",
};

export const CoachToast: React.FC<Props> = ({ feedback, visible, onClose }) => {
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!visible) setExpanded(false);
  }, [visible]);

  if (!feedback || !visible) return null;
  const sev = feedback.severity ?? "minor";
  const sevClass =
    sev === "blunder"
      ? "coach-blunder"
      : sev === "major"
      ? "coach-major"
      : sev === "minor"
      ? "coach-minor"
      : "coach-ok";

  return (
    <div className={`coach-toast ${sevClass}`} role="alert">
      <div className="coach-toast-header">
        <div className="coach-toast-icon">
          <span aria-hidden>{SEV_ICON[sev] ?? "•"}</span>
        </div>
        <div className="coach-toast-title">
          <div className="coach-toast-meta">
            <span className="coach-toast-brand">🎓 GTO COACH</span>
            <span className={`coach-toast-sev sev-${sev}`}>{SEV_LABEL_VI[sev] ?? sev}</span>
          </div>
          <div className="coach-toast-headline">{feedback.headline}</div>
          {feedback.correct_action && (
            <div className="coach-toast-correct">
              GTO: <strong>{feedback.correct_action}</strong>
              {feedback.correct_size_bb != null && ` ${feedback.correct_size_bb}bb`}
            </div>
          )}
        </div>
        <button className="coach-toast-close" onClick={onClose} title="Đóng" aria-label="Close">
          ✕
        </button>
      </div>
      {expanded ? (
        <div className="coach-toast-detail">
          {feedback.detail.split("\n").map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
      ) : (
        <button className="coach-toast-expand" onClick={() => setExpanded(true)}>
          Xem giải thích chi tiết →
        </button>
      )}
    </div>
  );
};
