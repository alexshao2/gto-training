import React, { useEffect, useState } from "react";
import { useSession } from "../store/session";
import type { CreateSessionRequest } from "../types/api";

const DEFAULT_PROFILES = ["tag", "lag", "fish", "nit", "gto"];

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
        <h1>Poker GTO Coach</h1>
        <p>Train MTT/cash 6-max với AI bots + HLV GTO realtime</p>
      </header>

      <section className="card-section">
        <h3>Tournament structure</h3>
        <div className="row">
          <button
            className={"chip " + (structure === "turbo" ? "chip-on" : "")}
            onClick={() => setStructure("turbo")}
          >
            Turbo
          </button>
          <button
            className={"chip " + (structure === "regular" ? "chip-on" : "")}
            onClick={() => setStructure("regular")}
          >
            Regular
          </button>
        </div>
      </section>

      <section className="card-section">
        <h3>Starting stack</h3>
        <div className="row">
          {[5000, 10000, 20000, 50000].map((s) => (
            <button
              key={s}
              className={"chip " + (stack === s ? "chip-on" : "")}
              onClick={() => setStack(s)}
            >
              {s.toLocaleString()}
            </button>
          ))}
        </div>
      </section>

      <section className="card-section">
        <h3>Số player ({nPlayers})</h3>
        <input
          type="range"
          min={2}
          max={6}
          value={nPlayers}
          onChange={(e) => setNPlayers(parseInt(e.target.value, 10))}
        />
      </section>

      <section className="card-section">
        <h3>Bot profiles tại bàn</h3>
        <p className="hint">Chọn các player type bạn muốn đối đầu (rotate quanh bàn).</p>
        <div className="profiles">
          {Object.entries(profiles).map(([key, label]) => (
            <button
              key={key}
              className={"profile-card " + (picked.includes(key) ? "picked" : "")}
              onClick={() => togglePicked(key)}
            >
              <strong>{key.toUpperCase()}</strong>
              <span>{label}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="card-section">
        <h3>Coach realtime</h3>
        <label className="row toggle">
          <input
            type="checkbox"
            checked={coachOn}
            onChange={(e) => setCoachOn(e.target.checked)}
          />
          <span>Bật coach (chỉ ra sai lầm khỏi GTO)</span>
        </label>
        <label className="row toggle">
          <input
            type="checkbox"
            checked={llmOn}
            onChange={(e) => setLlmOn(e.target.checked)}
            disabled={!coachOn}
          />
          <span>Dùng LLM để giải thích sâu hơn (cần API key)</span>
        </label>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <button
        className="btn-start"
        disabled={loading}
        onClick={handleStart}
      >
        {loading ? "Đang setup..." : "Bắt đầu giải đấu"}
      </button>
    </div>
  );
};
