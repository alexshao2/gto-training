import React from "react";

interface Props {
  card: string | null; // e.g. "Ah", null for unknown back
  small?: boolean;
}

const SUIT_CHAR: Record<string, string> = {
  h: "♥",
  d: "♦",
  c: "♣",
  s: "♠",
};

const SUIT_COLOR: Record<string, string> = {
  h: "#ef4444",
  d: "#3b82f6",
  c: "#10b981",
  s: "#1f2937",
};

export const PlayingCard: React.FC<Props> = ({ card, small }) => {
  if (!card) {
    return (
      <div className={"card card-back" + (small ? " card-small" : "")}>
        <div className="card-back-pattern" />
      </div>
    );
  }
  const rank = card[0];
  const suit = card[1];
  const display = rank === "T" ? "10" : rank;
  return (
    <div
      className={"card" + (small ? " card-small" : "")}
      style={{ color: SUIT_COLOR[suit] }}
    >
      <div className="card-rank">{display}</div>
      <div className="card-suit">{SUIT_CHAR[suit]}</div>
    </div>
  );
};
