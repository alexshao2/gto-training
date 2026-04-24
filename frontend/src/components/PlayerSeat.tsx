import React from "react";
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

function avatarFor(p: PlayerPublic): string {
  if (p.is_human) return PROFILE_AVATAR.human;
  return PROFILE_AVATAR[p.profile] ?? "🎭";
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
  const cardSize = player.is_human ? "md" : "sm";

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
        <div className="seat-avatar">{avatarFor(player)}</div>
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
        <div className="seat-winner-badge">WINNER 🏆</div>
      )}
    </div>
  );
};
