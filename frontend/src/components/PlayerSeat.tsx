import React, { useMemo } from "react";
import type { PlayerPublic } from "../types/api";
import { PlayingCard } from "./Card";

interface Props {
  player: PlayerPublic;
  isToAct: boolean;
  isButton: boolean;
  isWinner: boolean;
  position: string;
  bigBlind: number;
  showdownReveal?: boolean;
}

const ACTION_LABELS: Record<string, string> = {
  fold: "FOLD",
  check: "CHECK",
  call: "CALL",
  bet: "BET",
  raise: "RAISE",
  all_in: "ALL-IN",
};

const PROFILE_AVATAR: Record<string, string> = {
  human: "🧑",
  nit: "🦉",
  rock: "🗿",
  tag: "🦅",
  lag: "🐯",
  fish: "🐟",
  maniac: "🤡",
  gto: "🤖",
};

const CONFETTI_COLORS = ["#fbbf24", "#10b981", "#f87171", "#60a5fa", "#a78bfa", "#fde58a"];

function avatarFor(p: PlayerPublic): string {
  if (p.is_human) return PROFILE_AVATAR.human;
  return PROFILE_AVATAR[p.profile] ?? "🎭";
}

function Confetti() {
  // Pre-compute particles once per mount
  const particles = useMemo(() => {
    return Array.from({ length: 18 }).map((_, i) => {
      const angle = (i / 18) * Math.PI * 2 + Math.random() * 0.4;
      const distance = 60 + Math.random() * 60;
      const tx = Math.cos(angle) * distance;
      const ty = Math.sin(angle) * distance - 20; // slight upward bias
      const rot = (Math.random() * 720 - 360).toFixed(0) + "deg";
      const color = CONFETTI_COLORS[i % CONFETTI_COLORS.length];
      const delay = (Math.random() * 0.15).toFixed(2) + "s";
      return { tx, ty, rot, color, delay };
    });
  }, []);
  return (
    <div className="confetti">
      {particles.map((p, i) => (
        <span
          key={i}
          style={{
            background: p.color,
            ["--tx" as never]: `${p.tx}px`,
            ["--ty" as never]: `${p.ty}px`,
            ["--rot" as never]: p.rot,
            animationDelay: p.delay,
          }}
        />
      ))}
    </div>
  );
}

export const PlayerSeat: React.FC<Props> = ({
  player,
  isToAct,
  isButton,
  isWinner,
  position,
  bigBlind,
  showdownReveal,
}) => {
  const stackBB = bigBlind > 0 ? (player.stack / bigBlind).toFixed(0) : "0";
  const dimmed = player.folded || player.stack === 0;
  const showCards = player.cards != null;
  const cardSize = player.is_human ? "lg" : "sm";

  return (
    <div
      className={
        "seat" +
        (isToAct ? " seat-active" : "") +
        (dimmed ? " seat-dim" : "") +
        (player.is_human ? " seat-hero" : "") +
        (isWinner ? " seat-winner" : "")
      }
    >
      {showCards ? (
        <div className="seat-cards">
          {player.cards!.map((c, i) => (
            <PlayingCard
              key={i}
              card={c}
              size={cardSize}
              flipping={showdownReveal && !player.is_human}
            />
          ))}
        </div>
      ) : !player.folded && player.stack > 0 ? (
        <div className="seat-cards">
          <PlayingCard card={null} size={cardSize} />
          <PlayingCard card={null} size={cardSize} />
        </div>
      ) : null}

      <div className="seat-card">
        <div className="seat-avatar">
          {avatarFor(player)}
          {isToAct && !player.folded && (
            <div className="timer-ring">
              <svg viewBox="0 0 50 50">
                <circle cx="25" cy="25" r="22" />
              </svg>
            </div>
          )}
        </div>
        <div className="seat-info">
          <div className="seat-name">
            {player.name}
            {isButton && <span className="badge badge-btn" title="Dealer button">D</span>}
          </div>
          <div className="seat-pos">{position}</div>
          <div className="seat-stack">
            <span className="stack-amt">{player.stack.toLocaleString()}</span>
            <span className="stack-bb">{stackBB}bb</span>
          </div>
        </div>
      </div>

      {isToAct && !player.folded && (
        <div className="seat-thinking">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
        </div>
      )}

      {player.last_action && (
        <div className={`seat-action act-${player.last_action.type}`}>
          {ACTION_LABELS[player.last_action.type] ?? player.last_action.type}
          {player.last_action.amount > 0 && player.last_action.type !== "fold" &&
            ` ${player.last_action.amount.toLocaleString()}`}
        </div>
      )}

      {player.all_in && <div className="seat-tag seat-tag-allin">ALL-IN</div>}
      {player.folded && <div className="seat-tag seat-tag-fold">FOLDED</div>}

      {player.bet_this_street > 0 && (
        <div className="seat-bet-chips">
          <div className="bet-chip" />
          <div className="bet-amount">{player.bet_this_street.toLocaleString()}</div>
        </div>
      )}

      {isWinner && (
        <>
          <Confetti />
          <div className="seat-winner-badge">WINNER 🏆</div>
        </>
      )}
    </div>
  );
};
