import React from "react";

interface Props {
  card: string | null; // e.g. "Ah", null for unknown back
  size?: "lg" | "md" | "sm";
  flipping?: boolean;
}

const SUIT_CHAR: Record<string, string> = {
  h: "♥",
  d: "♦",
  c: "♣",
  s: "♠",
};

const SUIT_COLOR: Record<string, string> = {
  h: "#dc2626",
  d: "#dc2626",
  c: "#0f172a",
  s: "#0f172a",
};

export const PlayingCard: React.FC<Props> = ({ card, size = "md", flipping }) => {
  const sizeClass = `card-${size}`;
  if (!card) {
    return (
      <div className={`card card-back ${sizeClass}`}>
        <div className="card-back-pattern">
          <div className="card-back-logo">♣</div>
        </div>
      </div>
    );
  }
  const rank = card[0];
  const suit = card[1];
  const display = rank === "T" ? "10" : rank;
  const color = SUIT_COLOR[suit];
  const suitChar = SUIT_CHAR[suit];
  return (
    <div
      className={`card card-face ${sizeClass}${flipping ? " card-flip" : ""}`}
      style={{ color }}
    >
      <div className="card-corner card-corner-tl">
        <span className="card-rank">{display}</span>
        <span className="card-suit-small">{suitChar}</span>
      </div>
      <div className="card-suit-center">{suitChar}</div>
      <div className="card-corner card-corner-br">
        <span className="card-rank">{display}</span>
        <span className="card-suit-small">{suitChar}</span>
      </div>
    </div>
  );
};
