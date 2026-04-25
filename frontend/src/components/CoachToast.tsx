import React, { useEffect, useRef, useState } from "react";
import type { CoachFeedback } from "../types/api";
import {
  isPlaying,
  isVoiceEnabled,
  onPlayingChange,
  playFromUrl,
  speakText,
  stop as stopVoice,
} from "../utils/voice";

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
  const [playing, setPlaying] = useState(isPlaying());
  const lastSpokenUrl = useRef<string | null>(null);

  useEffect(() => onPlayingChange(setPlaying), []);

  useEffect(() => {
    if (!visible) setExpanded(false);
  }, [visible]);

  // Auto-play whenever a NEW feedback arrives with an audio_url.
  useEffect(() => {
    if (!visible || !feedback?.audio_url) return;
    if (lastSpokenUrl.current === feedback.audio_url) return;
    lastSpokenUrl.current = feedback.audio_url;
    void playFromUrl(feedback.audio_url);
  }, [visible, feedback?.audio_url]);

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

  const voiceOn = isVoiceEnabled();
  const hasAudio = !!feedback.audio_url;

  const toggleAudio = () => {
    if (playing) {
      stopVoice();
      return;
    }
    if (feedback.audio_url) {
      void playFromUrl(feedback.audio_url);
    }
  };

  const speakDetail = () => {
    if (feedback.detail) void speakText(feedback.detail);
  };

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
        {voiceOn && hasAudio && (
          <button
            className={`coach-toast-voice ${playing ? "playing" : ""}`}
            onClick={toggleAudio}
            title={playing ? "Tạm dừng" : "Nghe lại"}
            aria-label={playing ? "Pause voice" : "Play voice"}
          >
            {playing ? "⏸" : "🔊"}
          </button>
        )}
        <button className="coach-toast-close" onClick={onClose} title="Đóng" aria-label="Close">
          ✕
        </button>
      </div>
      {expanded ? (
        <div className="coach-toast-detail">
          {feedback.detail.split("\n").map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          {voiceOn && (
            <button className="coach-toast-detail-voice" onClick={speakDetail}>
              🔊 Đọc giải thích chi tiết
            </button>
          )}
        </div>
      ) : (
        <button className="coach-toast-expand" onClick={() => setExpanded(true)}>
          Xem giải thích chi tiết →
        </button>
      )}
    </div>
  );
};
