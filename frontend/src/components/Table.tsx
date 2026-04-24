import React from "react";
import type { SessionSnapshot } from "../types/api";
import { PlayingCard } from "./Card";
import { PlayerSeat } from "./PlayerSeat";
import { ActionBar } from "./ActionBar";
import { CoachPanel } from "./CoachPanel";
import { useSession } from "../store/session";
import { hapticNotify } from "../utils/telegram";

interface Props {
  snapshot: SessionSnapshot;
}

const POS_6 = ["BTN", "SB", "BB", "UTG", "HJ", "CO"];

function positionLabel(seat: number, btn: number, n: number): string {
  if (n === 6) {
    const offset = (seat - btn + 6) % 6;
    return POS_6[offset];
  }
  if (n === 2) return seat === btn ? "BTN/SB" : "BB";
  // Generic: rotate from BTN
  return `S${seat}`;
}

export const Table: React.FC<Props> = ({ snapshot }) => {
  const { act, newHand, reset } = useSession();
  const state = snapshot.state;
  if (!state) {
    return <div>Loading...</div>;
  }

  const heroSeat = snapshot.config.hero_seat;
  const heroPlayer = state.players.find((p) => p.is_human);
  const tableN = state.players.length;

  const handleAction = async (a: string, amount?: number) => {
    await act(a as any, amount);
    if (snapshot.last_coach?.is_mistake) {
      hapticNotify("error");
    }
  };

  const onNextHand = () => {
    if (snapshot.tournament_over) {
      reset();
    } else {
      newHand();
    }
  };

  // Arrange seats around the table: hero at bottom-center, others rotate
  const orderedSeats = [...state.players].sort((a, b) => {
    // Hero at the bottom (index 0), others fill clockwise
    const offA = (a.seat - heroSeat + tableN) % tableN;
    const offB = (b.seat - heroSeat + tableN) % tableN;
    return offA - offB;
  });

  // Positions around an oval (6 slots): bottom, bottom-left, top-left, top, top-right, bottom-right
  const ovalPositions: Record<number, { x: number; y: number }[]> = {
    2: [
      { x: 50, y: 80 },
      { x: 50, y: 15 },
    ],
    3: [
      { x: 50, y: 80 },
      { x: 15, y: 30 },
      { x: 85, y: 30 },
    ],
    4: [
      { x: 50, y: 82 },
      { x: 12, y: 50 },
      { x: 50, y: 12 },
      { x: 88, y: 50 },
    ],
    5: [
      { x: 50, y: 82 },
      { x: 10, y: 55 },
      { x: 28, y: 15 },
      { x: 72, y: 15 },
      { x: 90, y: 55 },
    ],
    6: [
      { x: 50, y: 82 },
      { x: 12, y: 60 },
      { x: 18, y: 18 },
      { x: 50, y: 8 },
      { x: 82, y: 18 },
      { x: 88, y: 60 },
    ],
  };

  const seatPositions = ovalPositions[tableN] ?? ovalPositions[6];

  return (
    <div className="table-screen">
      <header className="topbar">
        <div className="topbar-left">
          <span className="hand-no">Hand #{snapshot.hand_no}</span>
          <span className="level">
            Lv {snapshot.level_index + 1}: {state.small_blind}/{state.big_blind}
            {state.ante > 0 && <> ({state.ante})</>}
          </span>
        </div>
        <div className="topbar-right">
          <span className="alive">{snapshot.tournament_players_alive} left</span>
          <button className="exit-btn" onClick={() => reset()}>
            ✕
          </button>
        </div>
      </header>

      <div className="oval">
        <div className="board">
          <div className="pot">Pot: {state.pot.toLocaleString()}</div>
          <div className="board-cards">
            {state.board.map((c, i) => (
              <PlayingCard key={i} card={c} />
            ))}
            {Array.from({ length: 5 - state.board.length }).map((_, i) => (
              <div key={`ph-${i}`} className="card card-placeholder" />
            ))}
          </div>
          <div className="street">{state.street.toUpperCase()}</div>
        </div>

        {orderedSeats.map((p, i) => {
          const pos = seatPositions[i] ?? { x: 50, y: 50 };
          const isToAct = state.to_act_seat === p.seat;
          const isButton = state.button_seat === p.seat;
          const positionLabelStr = positionLabel(p.seat, state.button_seat, tableN);
          return (
            <div
              key={p.seat}
              className="seat-wrap"
              style={{
                left: `${pos.x}%`,
                top: `${pos.y}%`,
              }}
            >
              <PlayerSeat
                player={p}
                isToAct={isToAct}
                isButton={isButton}
                position={positionLabelStr}
                bigBlind={state.big_blind}
              />
            </div>
          );
        })}
      </div>

      <CoachPanel
        feedback={snapshot.last_coach}
        enabled={snapshot.config.coach_enabled}
      />

      {snapshot.tournament_over ? (
        <div className="game-over">
          <h2>Giải đấu kết thúc</h2>
          <p>
            {heroPlayer && heroPlayer.stack > 0
              ? "🏆 Bạn vô địch!"
              : "Bạn đã bust. Thử lại để cải thiện GTO range."}
          </p>
          <button className="btn-start" onClick={onNextHand}>
            Về lobby
          </button>
        </div>
      ) : snapshot.hand_complete ? (
        <div className="hand-complete">
          <div>
            <strong>Hand kết thúc.</strong>{" "}
            {state.winners.map((w) => (
              <span key={w.seat}>
                Seat {w.seat} thắng {w.amount.toLocaleString()} ({w.reason})
              </span>
            ))}
          </div>
          <button className="btn-next" onClick={onNextHand}>
            Hand tiếp theo →
          </button>
        </div>
      ) : snapshot.legal_actions ? (
        <ActionBar
          legal={snapshot.legal_actions}
          bigBlind={state.big_blind}
          onAction={handleAction}
          disabled={false}
        />
      ) : (
        <div className="waiting">
          <span className="spinner" />
          <span>Đang chờ AI bots...</span>
        </div>
      )}
    </div>
  );
};
