import React, { useState } from "react";

const STORAGE_KEY = "gto_tutorial_seen_v1";

export function hasSeenTutorial(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function markTutorialSeen() {
  try {
    localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    /* ignore */
  }
}

interface Step {
  icon: string;
  title: string;
  body: string;
  visual: React.ReactNode;
}

const STEPS: Step[] = [
  {
    icon: "🃏",
    title: "Bàn đấu MTT 6-max",
    body:
      "Bạn ngồi vị trí dưới cùng. 5 đối thủ là AI bot với phong cách khác nhau (tight, loose, fish, GTO solver). Mục tiêu: sống sót lâu nhất + về top 3 để ăn tiền giải.",
    visual: (
      <div className="tut-table">
        <div className="tut-felt">
          <span className="tut-bot tut-bot-1">🦅</span>
          <span className="tut-bot tut-bot-2">🐯</span>
          <span className="tut-bot tut-bot-3">🐟</span>
          <span className="tut-bot tut-bot-4">🦉</span>
          <span className="tut-bot tut-bot-5">🤖</span>
          <span className="tut-pot">POT</span>
          <span className="tut-bot tut-hero">🧑</span>
        </div>
      </div>
    ),
  },
  {
    icon: "🎯",
    title: "Coach realtime",
    body:
      "Mỗi khi bạn fold/call/raise, AI HLV sẽ đánh giá ngay: nếu lệch GTO sẽ giải thích bằng tiếng Việt — fold quá lỏng, raise sai size, miss value bet. Cứ chơi rồi học.",
    visual: (
      <div className="tut-toast">
        <div className="tut-toast-head">
          <span className="tut-toast-icon">⚠️</span>
          <span>Sai lầm: Open quá rộng UTG</span>
        </div>
        <div className="tut-toast-body">
          GTO range UTG ~12%. Bạn vừa raise A2o — hand này nên fold preflop từ early position.
        </div>
      </div>
    ),
  },
  {
    icon: "🔊",
    title: "Voice coach",
    body:
      "Bật voice ở phần \"Coach realtime\" để AI ĐỌC feedback bằng tiếng Việt khi bạn đang chơi. Vừa chơi vừa học, không cần dừng lại đọc text.",
    visual: (
      <div className="tut-voice">
        <div className="tut-voice-icon">🔊</div>
        <div className="tut-voice-bars">
          <span /><span /><span /><span /><span /><span /><span />
        </div>
        <div className="tut-voice-cap">"Pre-flop, UTG nên fold A2o..."</div>
      </div>
    ),
  },
  {
    icon: "🚀",
    title: "Sẵn sàng?",
    body:
      "Tip: hand đầu thường khó vì bạn chưa đọc được bot. Đừng sợ fold, đừng tilt khi bị suckout. Coach sẽ chỉ ra leak sau ~10-20 hand đầu tiên.",
    visual: (
      <div className="tut-go">
        <div className="tut-go-emoji">🎲</div>
        <div className="tut-go-tip">
          Bấm <strong>Bắt đầu giải đấu</strong> ở Lobby để vào bàn.
        </div>
      </div>
    ),
  },
];

interface Props {
  onDismiss: () => void;
}

export const Tutorial: React.FC<Props> = ({ onDismiss }) => {
  const [step, setStep] = useState(0);
  const last = step === STEPS.length - 1;
  const cur = STEPS[step];

  const close = () => {
    markTutorialSeen();
    onDismiss();
  };

  return (
    <div className="tut-backdrop" role="dialog" aria-modal="true">
      <div className="tut-modal">
        <button className="tut-skip" onClick={close} aria-label="Bỏ qua">
          Bỏ qua
        </button>

        <div className="tut-progress">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className={"tut-pip" + (i === step ? " tut-pip-on" : "")}
            />
          ))}
        </div>

        <div className="tut-visual">{cur.visual}</div>

        <div className="tut-icon">{cur.icon}</div>
        <h2 className="tut-title">{cur.title}</h2>
        <p className="tut-body">{cur.body}</p>

        <div className="tut-actions">
          {step > 0 && (
            <button className="tut-btn tut-btn-back" onClick={() => setStep((s) => s - 1)}>
              ← Quay lại
            </button>
          )}
          <button
            className="tut-btn tut-btn-next"
            onClick={() => (last ? close() : setStep((s) => s + 1))}
          >
            {last ? "Bắt đầu" : "Tiếp →"}
          </button>
        </div>
      </div>
    </div>
  );
};
