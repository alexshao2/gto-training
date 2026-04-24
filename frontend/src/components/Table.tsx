import React, { useEffect, useMemo, useRef, useState } from "react";
import type { SessionSnapshot } from "../types/api";
import { PlayingCard } from "./Card";
import { PlayerSeat } from "./PlayerSeat";
import { ActionBar } from "./ActionBar";
import { CoachToast } from "./CoachToast";
import { TournamentHud } from "./TournamentHud";
import { useSession } from "../store/session";
import { hapticNotify } from "../utils/telegram";
import { sfx } from "../utils/sound";

interface Props {
  snapshot: SessionSnapshot;
}

const POS_6 = ["BTN", "SB", "BB", "UTG", "HJ", "CO"];

function positionLabel(seat: number, btn: number, n: number): string {
  if (n === 6) return POS_6[(seat - btn + 6) % 6];
  if (n === 2) return seat === btn ? "BTN/SB" : "BB";
  return `S${seat}`;
}

const OVAL_POSITIONS: Record<number, { x: number; y: number }[]> = {
  2: [{ x: 50, y: 80 }, { x: 50, y: 18 }],
  3: [{ x: 50, y: 80 }, { x: 14, y: 35 }, { x: 86, y: 35 }],
  4: [{ x: 50, y: 82 }, { x: 12, y: 50 }, { x: 50, y: 14 }, { x: 88, y: 50 }],
  5: [
    { x: 50, y: 82 }, { x: 10, y: 58 }, { x: 28, y: 18 },
    { x: 72, y: 18 }, { x: 90, y: 58 },
  ],
  6: [
    { x: 50, y: 84 }, { x: 12, y: 62 }, { x: 18, y: 22 },
    { x: 50, y: 12 }, { x: 82, y: 22 }, { x: 88, y: 62 },
  ],
};

export const Table: React.FC<Props> = ({ snapshot }) => {
  const { act, newHand, reset } = useSession();
  const state = snapshot.state;
  const [showCoach, setShowCoach] = useState(false);
  const lastCoachTsRef = useRef<string>("");

  // Auto-show coach on new mistake
  useEffect(() => {
    const c = snapshot.last_coach;
    if (!c) return;
    const sig = `${c.headline}|${c.detail}`;
    if (sig !== lastCoachTsRef.current && c.is_mistake) {
      lastCoachTsRef.current = sig;
      setShowCoach(true);
      hapticNotify("warning");
      sfx.warn();
    }
  }, [snapshot.last_coach]);

  // Auto-dismiss coach toast when a new hand starts (so we don't show stale advice)
  const lastSeenHandRef = useRef<number>(snapshot.hand_no);
  useEffect(() => {
    if (snapshot.hand_no !== lastSeenHandRef.current) {
      lastSeenHandRef.current = snapshot.hand_no;
      setShowCoach(false);
    }
  }, [snapshot.hand_no]);

  // Bot action sound: detect last_action change on non-hero seats
  const lastActionsRef = useRef<Record<number, string>>({});
  useEffect(() => {
    if (!state) return;
    for (const p of state.players) {
      const sig = p.last_action ? `${p.last_action.type}:${p.last_action.amount}` : "";
      const prev = lastActionsRef.current[p.seat];
      if (sig && sig !== prev) {
        lastActionsRef.current[p.seat] = sig;
        if (!p.is_human && prev != null) {
          // Skip first-time set (initial render) but always for subsequent changes
          switch (p.last_action!.type) {
            case "fold": sfx.fold(); break;
            case "check": sfx.check(); break;
            case "call": sfx.chipSlide(); break;
            case "bet":
            case "raise": sfx.chipClink(); break;
            case "all_in": sfx.allIn(); break;
          }
        }
      }
    }
  }, [state]);

  // Board reveal sound: detect new community card
  const lastBoardLenRef = useRef<number>(0);
  useEffect(() => {
    if (!state) {
      lastBoardLenRef.current = 0;
      return;
    }
    const len = state.board.length;
    if (len > lastBoardLenRef.current) {
      sfx.cardDeal();
      // Subtle stagger for multi-card reveal (flop)
      const newCount = len - lastBoardLenRef.current;
      if (newCount > 1) {
        for (let i = 1; i < newCount; i++) {
          window.setTimeout(() => sfx.cardDeal(), i * 110);
        }
      }
    }
    lastBoardLenRef.current = len;
  }, [state]);

  // Hand complete: win/lose sound based on hero's seat
  const lastHandRef = useRef<number>(0);
  useEffect(() => {
    if (!state || !snapshot.hand_complete) return;
    if (snapshot.hand_no === lastHandRef.current) return;
    lastHandRef.current = snapshot.hand_no;
    const heroSeat = snapshot.config.hero_seat;
    const heroWon = state.winners.some((w) => w.seat === heroSeat);
    if (heroWon) {
      sfx.win();
      hapticNotify("success");
    } else {
      // Only "lose" sound if hero was in the hand (not folded earlier and not bust)
      const hero = state.players.find((p) => p.seat === heroSeat);
      if (hero && !hero.folded && hero.stack > 0) {
        sfx.lose();
      }
    }
  }, [snapshot.hand_complete, snapshot.hand_no, state, snapshot.config.hero_seat]);

  // Auto-deal next hand a few seconds after hand_complete (so user can see showdown)
  const autoNextRef = useRef<number | null>(null);
  useEffect(() => {
    if (snapshot.hand_complete && !snapshot.tournament_over) {
      if (autoNextRef.current) window.clearTimeout(autoNextRef.current);
      autoNextRef.current = window.setTimeout(() => {
        sfx.cardDeal();
        newHand();
      }, 4500);
    }
    return () => {
      if (autoNextRef.current) {
        window.clearTimeout(autoNextRef.current);
        autoNextRef.current = null;
      }
    };
  }, [snapshot.hand_complete, snapshot.tournament_over, snapshot.hand_no]);

  const winnerSeats = useMemo(() => {
    if (!state) return new Set<number>();
    return new Set(state.winners.map((w) => w.seat));
  }, [state]);

  if (!state) {
    return <div className="loading-screen">Đang tải bàn...</div>;
  }

  const heroSeat = snapshot.config.hero_seat;
  const heroPlayer = state.players.find((p) => p.is_human);
  const tableN = state.players.length;

  const orderedSeats = [...state.players].sort((a, b) => {
    const offA = (a.seat - heroSeat + tableN) % tableN;
    const offB = (b.seat - heroSeat + tableN) % tableN;
    return offA - offB;
  });

  const seatPositions = OVAL_POSITIONS[tableN] ?? OVAL_POSITIONS[6];
  const showdownReveal = state.street === "showdown" || state.street === "complete";

  return (
    <div className="table-screen">
      <TournamentHud snapshot={snapshot} onExit={() => reset()} />

      <div className="felt">
        <div className="felt-rim" />
        <div className="felt-inner">
          {/* Center: pot + community board */}
          <div className="board">
            <div className="board-cards">
              {Array.from({ length: 5 }).map((_, i) => {
                const c = state.board[i];
                return c ? (
                  <PlayingCard key={i} card={c} size="md" />
                ) : (
                  <div key={`ph-${i}`} className="card card-md card-placeholder" />
                );
              })}
            </div>
            <div className="pot">
              <div className="pot-label">POT</div>
              <div className="pot-amount">{state.pot.toLocaleString()}</div>
              <div className="pot-bb">{(state.pot / Math.max(state.big_blind, 1)).toFixed(1)} bb</div>
            </div>
            <div className="street-tag">{state.street.toUpperCase()}</div>
          </div>

          {/* Seats around the oval */}
          {orderedSeats.map((p, i) => {
            const pos = seatPositions[i] ?? { x: 50, y: 50 };
            const isToAct = state.to_act_seat === p.seat;
            const isButton = state.button_seat === p.seat;
            const isWinner = winnerSeats.has(p.seat);
            const positionLabelStr = positionLabel(p.seat, state.button_seat, tableN);
            return (
              <div
                key={p.seat}
                className="seat-wrap"
                style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
              >
                <PlayerSeat
                  player={p}
                  isToAct={isToAct}
                  isButton={isButton}
                  isWinner={isWinner}
                  position={positionLabelStr}
                  bigBlind={state.big_blind}
                  showdownReveal={showdownReveal}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Coach toast (auto-shows on mistake) */}
      <CoachToast
        feedback={snapshot.last_coach}
        visible={showCoach}
        onClose={() => setShowCoach(false)}
      />

      {/* Bottom controls */}
      {snapshot.tournament_over ? (
        <div className="game-over">
          <div className="game-over-card">
            <h2>{heroPlayer && heroPlayer.stack > 0 ? "🏆 Bạn vô địch!" : "💀 Bạn đã bust"}</h2>
            <p>
              {heroPlayer && heroPlayer.stack > 0
                ? "Tuyệt vời! Quay lại lobby để chơi giải mới."
                : `Bạn về thứ ${snapshot.hero_rank ?? "?"}/${snapshot.config.n_players}. Tiếp tục train để cải thiện GTO range.`}
            </p>
            <button className="btn-start" onClick={() => reset()}>
              Về lobby
            </button>
          </div>
        </div>
      ) : snapshot.hand_complete ? (
        <div className="hand-complete-banner">
          <div className="winners-line">
            {state.winners.map((w) => {
              const wp = state.players.find((p) => p.seat === w.seat);
              return (
                <span key={w.seat}>
                  <strong>{wp?.name ?? `Seat ${w.seat}`}</strong> thắng{" "}
                  <strong>{w.amount.toLocaleString()}</strong> ({w.reason})
                </span>
              );
            })}
          </div>
          <button className="btn-next" onClick={() => newHand()}>
            Hand tiếp →
          </button>
          <span className="auto-hint">tự deal sau ~4s</span>
        </div>
      ) : snapshot.legal_actions ? (
        <ActionBar
          legal={snapshot.legal_actions}
          bigBlind={state.big_blind}
          onAction={(a, amt) => act(a as never, amt)}
          disabled={false}
        />
      ) : (
        <div className="waiting-bar">
          <span className="spinner" />
          <span>Đối thủ đang suy nghĩ...</span>
        </div>
      )}
    </div>
  );
};
