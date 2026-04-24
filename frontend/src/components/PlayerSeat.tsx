import React from "react";
import type { PlayerPublic } from "../types/api";
import { PlayingCard } from "./Card";

interface Props {
  player: PlayerPublic;
  isToAct: boolean;
  isButton: boolean;
  position: string;
  bigBlind: number;
}

const ACTION_LABELS: Record<string, string> = {
  fold: "Fold",
  check: "Check",
  call: "Call",
  bet: "Bet",
  raise: "Raise",
  all_in: "All-in",
};

export const PlayerSeat: React.FC<Props> = ({
  player,
  isToAct,
  isButton,
  position,
  bigBlind,
}) => {
  const stackBB = (player.stack / Math.max(bigBlind, 1)).toFixed(0);
  const dimmed = player.folded || player.stack === 0;
  return (
    <div
      className={
        "seat" +
        (isToAct ? " seat-active" : "") +
        (dimmed ? " seat-dim" : "") +
        (player.is_human ? " seat-hero" : "")
      }
    >
      <div className="seat-header">
        <span className="seat-name">{player.name}</span>
        {isButton && <span className="badge badge-btn">D</span>}
        <span className="badge badge-pos">{position}</span>
      </div>
      <div className="seat-cards">
        {player.cards
          ? player.cards.map((c, i) => (
              <PlayingCard key={i} card={c} small={!player.is_human} />
            ))
          : !player.folded && player.stack > 0
          ? [<PlayingCard key="0" card={null} small />, <PlayingCard key="1" card={null} small />]
          : null}
      </div>
      <div className="seat-stack">
        <span>{player.stack.toLocaleString()}</span>
        <span className="stack-bb">{stackBB}bb</span>
      </div>
      {player.bet_this_street > 0 && (
        <div className="seat-bet">{player.bet_this_street.toLocaleString()}</div>
      )}
      {player.last_action && (
        <div className="seat-action">
          {ACTION_LABELS[player.last_action.type] ?? player.last_action.type}
          {player.last_action.amount > 0 ? ` ${player.last_action.amount}` : ""}
        </div>
      )}
      {player.all_in && <div className="seat-tag">ALL-IN</div>}
      {player.folded && <div className="seat-tag seat-tag-fold">FOLDED</div>}
    </div>
  );
};
