import React from "react";
import type { SessionSnapshot } from "../types/api";

interface Props {
  snapshot: SessionSnapshot;
  onExit: () => void;
}

export const TournamentHud: React.FC<Props> = ({ snapshot, onExit }) => {
  const lvl = snapshot.level;
  const next = snapshot.next_level;
  const handsToNext = snapshot.hands_until_next_level ?? 0;
  const heroRank = snapshot.hero_rank ?? "?";
  const totalPlayers = snapshot.config.n_players;
  const alive = snapshot.tournament_players_alive;

  // Hero ICM equity (relative to virtual 1000-unit prize pool)
  const heroIcm = snapshot.icm.find((p) => {
    const tp = snapshot.table_players.find((tp) => tp.seat === p.seat);
    return tp?.is_human;
  });

  return (
    <div className="hud">
      <div className="hud-section hud-tourney">
        <div className="hud-row hud-row-strong">
          <span className="hud-pill hud-pill-rank">#{heroRank}/{totalPlayers}</span>
          <span className="hud-pill hud-pill-alive">{alive} còn lại</span>
        </div>
        <div className="hud-row">
          <span className="hud-label">Hand</span>
          <span className="hud-value">#{snapshot.hand_no}</span>
        </div>
      </div>

      <div className="hud-section hud-blinds">
        <div className="hud-row">
          <span className="hud-label">Lv {snapshot.level_index + 1}</span>
          <span className="hud-value-strong">
            {lvl.sb}/{lvl.bb}
            {lvl.ante > 0 && <span className="hud-ante">+{lvl.ante}</span>}
          </span>
        </div>
        <div className="hud-row hud-row-sub">
          {next ? (
            <span className="hud-next">
              Next: {next.sb}/{next.bb}
              {next.ante > 0 && `+${next.ante}`} (sau {handsToNext} hands)
            </span>
          ) : (
            <span className="hud-next">Final blind level</span>
          )}
        </div>
      </div>

      <div className="hud-section hud-prize">
        <div className="hud-row">
          <span className="hud-label">ICM</span>
          <span className="hud-value">
            {heroIcm ? `${heroIcm.icm_equity.toFixed(1)}%` : "—"}
          </span>
        </div>
        <div className="hud-row hud-row-sub">
          <span className="hud-prize-list">
            {(snapshot.prize_breakdown ?? []).slice(0, 3).map((p) => (
              <span key={p.place} className="prize-tier">
                {p.place === 1 ? "🥇" : p.place === 2 ? "🥈" : "🥉"} {p.pct}%
              </span>
            ))}
          </span>
        </div>
      </div>

      <button className="exit-btn" onClick={onExit} title="Về lobby">
        ✕
      </button>
    </div>
  );
};
