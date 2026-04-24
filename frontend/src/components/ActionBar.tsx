import React, { useState, useEffect } from "react";
import type { Action, LegalActions } from "../types/api";
import { hapticImpact } from "../utils/telegram";

interface Props {
  legal: LegalActions;
  bigBlind: number;
  onAction: (a: Action, amount?: number) => void;
  disabled: boolean;
}

const PRESETS: { label: string; mult: number }[] = [
  { label: "1/3 pot", mult: 0.33 },
  { label: "1/2 pot", mult: 0.5 },
  { label: "2/3 pot", mult: 0.66 },
  { label: "Pot", mult: 1.0 },
];

export const ActionBar: React.FC<Props> = ({ legal, bigBlind, onAction, disabled }) => {
  const canRaise = legal.actions.includes("raise") || legal.actions.includes("bet");
  const [raiseAmount, setRaiseAmount] = useState<number>(legal.min_raise_to);

  useEffect(() => {
    setRaiseAmount(legal.min_raise_to);
  }, [legal.min_raise_to]);

  const submit = (a: Action, amount?: number) => {
    hapticImpact("medium");
    onAction(a, amount);
  };

  const presetAmount = (mult: number): number => {
    const target = legal.current_bet + Math.round(legal.pot * mult);
    return Math.min(legal.max_raise_to, Math.max(legal.min_raise_to, target));
  };

  return (
    <div className="action-bar">
      <div className="action-row action-row-buttons">
        {legal.actions.includes("fold") && (
          <button
            className="btn btn-fold"
            disabled={disabled}
            onClick={() => submit("fold")}
          >
            Fold
          </button>
        )}
        {legal.actions.includes("check") && (
          <button
            className="btn btn-check"
            disabled={disabled}
            onClick={() => submit("check")}
          >
            Check
          </button>
        )}
        {legal.actions.includes("call") && (
          <button
            className="btn btn-call"
            disabled={disabled}
            onClick={() => submit("call")}
          >
            Call {legal.to_call.toLocaleString()}
            <span className="btn-sub">{(legal.to_call / Math.max(bigBlind, 1)).toFixed(1)}bb</span>
          </button>
        )}
        {canRaise && (
          <button
            className="btn btn-raise"
            disabled={disabled}
            onClick={() =>
              submit(
                legal.actions.includes("raise") ? "raise" : "bet",
                raiseAmount
              )
            }
          >
            {legal.actions.includes("raise") ? "Raise" : "Bet"} to {raiseAmount.toLocaleString()}
            <span className="btn-sub">{(raiseAmount / Math.max(bigBlind, 1)).toFixed(1)}bb</span>
          </button>
        )}
      </div>
      {canRaise && (
        <div className="action-row action-row-sizing">
          <div className="presets">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                className="preset"
                disabled={disabled}
                onClick={() => setRaiseAmount(presetAmount(p.mult))}
              >
                {p.label}
              </button>
            ))}
            <button
              className="preset"
              disabled={disabled}
              onClick={() => setRaiseAmount(legal.max_raise_to)}
            >
              All-in
            </button>
          </div>
          <input
            type="range"
            min={legal.min_raise_to}
            max={legal.max_raise_to}
            step={Math.max(1, Math.round(bigBlind / 2))}
            value={raiseAmount}
            onChange={(e) => setRaiseAmount(parseInt(e.target.value, 10))}
            disabled={disabled}
            className="slider"
          />
        </div>
      )}
    </div>
  );
};
