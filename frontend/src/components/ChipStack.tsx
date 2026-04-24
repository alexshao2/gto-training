import React from "react";

interface Props {
  amount: number;
  bigBlind?: number;
  compact?: boolean;
}

// Approximate chip denominations to visualize stack composition
const DENOMINATIONS: { value: number; color: string }[] = [
  { value: 5000, color: "#7c3aed" }, // purple
  { value: 1000, color: "#fbbf24" }, // gold
  { value: 500, color: "#3b82f6" }, // blue
  { value: 100, color: "#10b981" }, // green
  { value: 25, color: "#f87171" }, // red
  { value: 5, color: "#475569" }, // gray
  { value: 1, color: "#fff" },
];

function decompose(amount: number): { value: number; color: string; count: number }[] {
  const out: { value: number; color: string; count: number }[] = [];
  let rem = Math.floor(amount);
  for (const d of DENOMINATIONS) {
    if (rem >= d.value) {
      const count = Math.min(8, Math.floor(rem / d.value));
      if (count > 0) {
        out.push({ value: d.value, color: d.color, count });
        rem -= count * d.value;
      }
    }
  }
  return out.slice(0, 4); // cap visual stacks
}

export const ChipStack: React.FC<Props> = ({ amount, bigBlind, compact }) => {
  if (amount <= 0) return null;
  const stacks = decompose(amount);
  const bbStr = bigBlind ? ` (${(amount / bigBlind).toFixed(1)}bb)` : "";
  return (
    <div className={"chip-stack" + (compact ? " chip-stack-compact" : "")}>
      <div className="chip-stack-visual">
        {stacks.map((s, i) => (
          <div key={i} className="chip-column" style={{ left: `${i * 14}px` }}>
            {Array.from({ length: s.count }).map((_, j) => (
              <div
                key={j}
                className="chip"
                style={{
                  background: s.color,
                  bottom: `${j * 3}px`,
                  borderColor: s.color,
                }}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="chip-stack-label">
        {amount.toLocaleString()}
        {bbStr && <span className="chip-stack-bb">{bbStr}</span>}
      </div>
    </div>
  );
};
