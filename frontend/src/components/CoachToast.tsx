import React, { useEffect, useState } from "react";
import type { CoachFeedback } from "../types/api";

interface Props {
  feedback: CoachFeedback | null | undefined;
  visible: boolean;
  onClose: () => void;
}

export const CoachToast: React.FC<Props> = ({ feedback, visible, onClose }) => {
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!visible) setExpanded(false);
  }, [visible]);

  if (!feedback || !visible) return null;
  const sevClass =
    feedback.severity === "blunder"
      ? "coach-blunder"
      : feedback.severity === "major"
      ? "coach-major"
      : feedback.severity === "minor"
      ? "coach-minor"
      : "coach-ok";

  return (
    <div className={`coach-toast ${sevClass}`}>
      <div className="coach-toast-header">
        <div className="coach-toast-icon">
          {feedback.is_mistake ? "⚠️" : "✓"}
        </div>
        <div className="coach-toast-title">
          <div className="coach-toast-headline">{feedback.headline}</div>
          {feedback.correct_action && (
            <div className="coach-toast-correct">
              GTO: <strong>{feedback.correct_action}</strong>
              {feedback.correct_size_bb != null && ` ${feedback.correct_size_bb}bb`}
            </div>
          )}
        </div>
        <button className="coach-toast-close" onClick={onClose} title="Đóng">
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
