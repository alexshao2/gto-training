import React, { useEffect, useState } from "react";
import { useSession } from "../store/session";
import type { CreateSessionRequest } from "../types/api";

const DEFAULT_PROFILES = ["tag", "lag", "fish", "nit", "gto"];

const PROFILE_AVATARS: Record<string, string> = {
  nit: "🦉",
  rock: "🗿",
  tag: "🦅",
  lag: "🐯",
  fish: "🐟",
  maniac: "🤡",
  gto: "🤖",
};

export const Lobby: React.FC = () => {
  const { profiles, loadProfiles, startSession, loading, error } = useSession();
  const [structure, setStructure] = useState<"turbo" | "regular">("turbo");
  const [stack, setStack] = useState(10000);
  const [nPlayers, setNPlayers] = useState(6);
  const [picked, setPicked] = useState<string[]>(DEFAULT_PROFILES);
  const [coachOn, setCoachOn] = useState(true);
  const [llmOn, setLlmOn] = useState(true);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  const togglePicked = (p: string) => {
    setPicked((cur) =>
      cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]
    );
  };

  const handleStart = () => {
    const req: CreateSessionRequest = {
      structure,
      starting_stack: stack,
      n_players: nPlayers,
      hero_seat: 0,
      bot_profiles: picked.length ? picked : DEFAULT_PROFILES,
      payouts: [50, 30, 20],
      coach_enabled: coachOn,
      coach_llm_enabled: llmOn,
    };
    startSession(req);
  };

  return (
    <div className="lobby">
      <header className="lobby-header">
        <h1>♠ Poker GTO Coach ♥</h1>
        <p>Train MTT 6-max với AI bots cấp độ thực + HLV GTO realtime</p>
      </header>

      <section className="card-section">
        <h3>Cấu trúc giải</h3>
        <div className="row">
          <button
            className={"chip-btn " + (structure === "turbo" ? "active" : "")}
            onClick={() => setStructure("turbo")}
          >
            ⚡ Turbo
          </button>
          <button
            className={"chip-btn " + (structure === "regular" ? "active" : "")}
            onClick={() => setStructure("regular")}
          >
            🐢 Regular
          </button>
        </div>
        <p className="hint">Turbo: blind tăng nhanh, deep stack ngắn. Regular: chậm hơn, deeper play.</p>
      </section>

      <section className="card-section">
        <h3>Stack khởi đầu</h3>
        <div className="row">
          {[5000, 10000, 20000, 50000].map((s) => (
            <button
              key={s}
              className={"chip-btn " + (stack === s ? "active" : "")}
              onClick={() => setStack(s)}
            >
              {s.toLocaleString()}
            </button>
          ))}
        </div>
      </section>

      <section className="card-section">
        <h3>Số player tại bàn ({nPlayers})</h3>
        <input
          type="range"
          min={2}
          max={6}
          value={nPlayers}
          onChange={(e) => setNPlayers(parseInt(e.target.value, 10))}
          className="slider"
        />
        <p className="hint">2 = HU, 6 = full ring 6-max</p>
      </section>

      <section className="card-section">
        <h3>Bot profiles tại bàn</h3>
        <p className="hint">Chọn các loại đối thủ. Profile sẽ rotate quanh bàn.</p>
        <div className="profile-grid">
          {Object.entries(profiles).map(([key, label]) => (
            <button
              key={key}
              className={"profile-pill " + (picked.includes(key) ? "active" : "")}
              onClick={() => togglePicked(key)}
            >
              <span className="profile-avatar">{PROFILE_AVATARS[key] ?? "🎭"}</span>
              <span className="profile-name">{key.toUpperCase()}</span>
              <span className="profile-desc">{label}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="card-section">
        <h3>Coach realtime</h3>
        <label className="row toggle-row">
          <input
            type="checkbox"
            checked={coachOn}
            onChange={(e) => setCoachOn(e.target.checked)}
          />
          <span>Bật coach (chỉ ra sai lầm khỏi GTO)</span>
        </label>
        <label className="row toggle-row">
          <input
            type="checkbox"
            checked={llmOn}
            onChange={(e) => setLlmOn(e.target.checked)}
            disabled={!coachOn}
          />
          <span>LLM giải thích sâu (Vietnamese, GTO reasoning)</span>
        </label>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <button className="btn-start" disabled={loading} onClick={handleStart}>
        {loading ? "Đang setup..." : "🎯 Bắt đầu giải đấu"}
      </button>
    </div>
  );
};
