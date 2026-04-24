"""In-memory tournament session: a single MTT-style table where the user (hero)
plays against AI bots. Drives the hand loop, queries bot decisions, and
exposes coach feedback whenever the hero takes an action.
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field

from ..bots.profiles import PROFILE_LABELS, decide
from ..coach.coach import CoachFeedback, evaluate_action
from ..coach.llm import enrich_feedback
from ..poker.cards import hole_card_combo
from ..poker.state import Action, ActionType, HandState, Player, Street
from ..tournament.structure import STRUCTURES, _icm_recursive_closed


@dataclass
class TournamentConfig:
    structure: str = "turbo"  # "turbo" | "regular"
    starting_stack: int = 10000
    n_players: int = 6
    hero_seat: int = 0
    bot_profiles: list[str] = field(
        default_factory=lambda: ["tag", "lag", "fish", "nit", "gto"]
    )
    payouts: list[float] = field(default_factory=lambda: [50.0, 30.0, 20.0])
    auto_bot_delay_ms: int = 600
    coach_enabled: bool = True
    coach_llm_enabled: bool = True


@dataclass
class HandHistoryEntry:
    hand_no: int
    hero_seat: int
    hero_cards: list[str]
    board: list[str]
    pot: int
    hero_actions: list[dict]
    coach_feedback: list[dict]
    winners: list[dict]
    hero_pnl: int


class TournamentSession:
    def __init__(self, config: TournamentConfig) -> None:
        self.id = str(uuid.uuid4())
        self.config = config
        self.rng = random.Random()
        self.level_index = 0
        self.hand_no = 0
        self.button_seat = 0
        self.players: list[Player] = self._init_players()
        self.state: HandState | None = None
        self.events: list[dict] = []
        self.history: list[HandHistoryEntry] = []
        self.created_at = time.time()
        self.lock = asyncio.Lock()
        self.last_coach: CoachFeedback | None = None

    def _init_players(self) -> list[Player]:
        players: list[Player] = []
        for seat in range(self.config.n_players):
            if seat == self.config.hero_seat:
                players.append(
                    Player(
                        seat=seat,
                        name="You",
                        stack=self.config.starting_stack,
                        is_human=True,
                        profile="human",
                    )
                )
            else:
                profile = self.config.bot_profiles[
                    (seat - 1) % len(self.config.bot_profiles)
                ]
                players.append(
                    Player(
                        seat=seat,
                        name=f"Bot-{seat} ({profile})",
                        stack=self.config.starting_stack,
                        is_human=False,
                        profile=profile,
                    )
                )
        return players

    def current_level(self):
        struct = STRUCTURES[self.config.structure]
        return struct[min(self.level_index, len(struct) - 1)]

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.stack > 0]

    def _emit(self, etype: str, payload: dict) -> None:
        self.events.append(
            {"t": time.time(), "type": etype, "payload": payload}
        )

    # ---------------- public API ----------------
    def start_new_hand(self) -> dict:
        alive = self.alive_players()
        if len(alive) < 2:
            self._emit("tournament_over", {"survivors": [p.seat for p in alive]})
            return self.snapshot()
        self.hand_no += 1
        # Move button to next alive player
        n = len(self.players)
        # Find next alive seat after current button
        for _ in range(n):
            self.button_seat = (self.button_seat + 1) % n
            if self.players[self.button_seat].stack > 0:
                break
        # Reset only alive players for the hand; eliminated stay folded with stack=0
        active_players = [p for p in self.players if p.stack > 0]
        level = self.current_level()
        self.state = HandState.new_hand(
            players=active_players,
            button_seat=active_players.index(self.players[self.button_seat])
            if self.players[self.button_seat] in active_players
            else 0,
            small_blind=level.sb,
            big_blind=level.bb,
            ante=level.ante,
            rng=self.rng,
        )
        self._emit("hand_start", {"hand_no": self.hand_no, "level": level.__dict__})
        return self.snapshot()

    async def submit_hero_action(
        self, action_type: str, amount: int = 0
    ) -> dict:
        if not self.state:
            raise RuntimeError("No active hand")
        hero_seat_local = self._hero_seat_in_state()
        if hero_seat_local is None:
            raise RuntimeError("Hero not in current hand")
        if self.state.to_act_seat != hero_seat_local:
            raise RuntimeError("Not hero's turn")

        action = self._build_action(action_type, amount, hero_seat_local)

        # Coach evaluates BEFORE we mutate state
        coach_fb: CoachFeedback | None = None
        if self.config.coach_enabled:
            coach_fb = evaluate_action(self.state, hero_seat_local, action)
            if self.config.coach_llm_enabled and coach_fb.is_mistake:
                hero = self.state.players[hero_seat_local]
                coach_fb = await enrich_feedback(
                    coach_fb,
                    state_summary=self._coach_summary(hero_seat_local),
                    hero_combo=hole_card_combo(*hero.cards),
                )
            self.last_coach = coach_fb
            self._emit("coach", coach_fb.to_dict())

        self.state.apply_action(hero_seat_local, action)
        self._emit("action", {"seat": hero_seat_local, "action": action.to_dict(), "is_hero": True})
        return self.snapshot(coach_feedback=coach_fb)

    def _build_action(self, action_type: str, amount: int, seat: int) -> Action:
        legal = self.state.legal_actions(seat)
        if action_type == "fold":
            return Action(ActionType.FOLD)
        if action_type == "check":
            return Action(ActionType.CHECK)
        if action_type == "call":
            return Action(ActionType.CALL, amount=legal["to_call"])
        if action_type == "bet":
            target = max(amount, legal["min_raise_to"])
            target = min(target, legal["max_raise_to"])
            return Action(ActionType.BET, amount=target)
        if action_type == "raise":
            target = max(amount, legal["min_raise_to"])
            target = min(target, legal["max_raise_to"])
            return Action(ActionType.RAISE, amount=target)
        if action_type == "all_in":
            target = legal["max_raise_to"]
            return Action(ActionType.RAISE, amount=target)
        raise ValueError(f"Unknown action {action_type}")

    async def step_bots(self) -> dict:
        """Run bot actions until it's hero's turn or hand completes."""
        if not self.state:
            return self.snapshot()
        max_iter = 200
        while max_iter > 0 and self.state.street not in (Street.SHOWDOWN, Street.COMPLETE):
            seat = self.state.to_act_seat
            if seat is None:
                break
            player = self.state.players[seat]
            if player.is_human:
                break
            if player.folded or player.all_in:
                # Should not happen due to advance_turn, but guard
                break
            await asyncio.sleep(self.config.auto_bot_delay_ms / 1000)
            action = decide(self.state, seat, player.profile, self.rng)
            try:
                self.state.apply_action(seat, action)
            except ValueError:
                # Fall back to safe action
                legal = self.state.legal_actions(seat)
                if "check" in legal["actions"]:
                    self.state.apply_action(seat, Action(ActionType.CHECK))
                else:
                    self.state.apply_action(seat, Action(ActionType.FOLD))
            self._emit(
                "action",
                {"seat": seat, "action": player.last_action.to_dict() if player.last_action else None, "is_hero": False},
            )
            max_iter -= 1
        if self.state.street == Street.COMPLETE:
            self._finalize_hand()
        return self.snapshot()

    def _finalize_hand(self) -> None:
        # Persist to history
        if not self.state:
            return
        hero_seat_local = self._hero_seat_in_state()
        if hero_seat_local is None:
            return
        hero = self.state.players[hero_seat_local]
        # Compute hero pnl this hand
        winners = self.state.winners
        hero_won = sum(w["amount"] for w in winners if w["seat"] == hero.seat)
        hero_pnl = hero_won - hero.total_invested

        entry = HandHistoryEntry(
            hand_no=self.hand_no,
            hero_seat=hero.seat,
            hero_cards=[str(c) for c in hero.cards] if hero.cards else [],
            board=[str(c) for c in self.state.board],
            pot=sum(p.total_invested for p in self.state.players),
            hero_actions=[
                h for h in self.state.history if h["seat"] == hero_seat_local
            ],
            coach_feedback=[e["payload"] for e in self.events if e["type"] == "coach"][-10:],
            winners=winners,
            hero_pnl=hero_pnl,
        )
        self.history.append(entry)

        # Check level progression (every 10 hands roughly = next level)
        if self.hand_no > 0 and self.hand_no % 10 == 0:
            self.level_index = min(
                self.level_index + 1, len(STRUCTURES[self.config.structure]) - 1
            )

        # Sync alive flags: any player with stack 0 stays out
        for p in self.state.players:
            # Their stack is already updated in state; we mirror to top-level players list
            for top in self.players:
                if top.seat == p.seat:
                    top.stack = p.stack

        self._emit("hand_complete", {"winners": winners, "hero_pnl": hero_pnl})

    def _hero_seat_in_state(self) -> int | None:
        if not self.state:
            return None
        for i, p in enumerate(self.state.players):
            if p.is_human:
                return i
        return None

    def _coach_summary(self, hero_seat_local: int) -> dict:
        st = self.state
        if not st:
            return {}
        hero = st.players[hero_seat_local]
        return {
            "street": st.street.value,
            "board": [str(c) for c in st.board],
            "pot": st.pot,
            "current_bet": st.current_bet,
            "hero_position_idx": hero.seat,
            "hero_stack": hero.stack,
            "n_players_active": len([p for p in st.players if not p.folded]),
            "history": st.history,
            "level": self.current_level().__dict__,
        }

    def snapshot(self, coach_feedback: CoachFeedback | None = None) -> dict:
        hero_seat_local = self._hero_seat_in_state()
        legal = None
        if self.state and hero_seat_local is not None and self.state.to_act_seat == hero_seat_local:
            legal = self.state.legal_actions(hero_seat_local)
        # ICM equity (chip count among alive)
        alive = [p for p in self.players if p.stack > 0]
        icm = []
        if len(alive) > 1:
            stacks = [p.stack for p in alive]
            eq = _icm_recursive_closed(stacks, self.config.payouts)
            for p, e in zip(alive, eq):
                icm.append({"seat": p.seat, "name": p.name, "stack": p.stack, "icm_equity": round(e, 2)})

        return {
            "session_id": self.id,
            "hand_no": self.hand_no,
            "level": self.current_level().__dict__,
            "level_index": self.level_index,
            "tournament_players_alive": len(alive),
            "icm": icm,
            "config": {
                "structure": self.config.structure,
                "starting_stack": self.config.starting_stack,
                "n_players": self.config.n_players,
                "hero_seat": self.config.hero_seat,
                "bot_profiles": self.config.bot_profiles,
                "payouts": self.config.payouts,
                "coach_enabled": self.config.coach_enabled,
            },
            "table_players": [
                {
                    "seat": p.seat,
                    "name": p.name,
                    "stack": p.stack,
                    "is_human": p.is_human,
                    "profile": p.profile,
                    "profile_label": PROFILE_LABELS.get(p.profile, p.profile),
                    "alive": p.stack > 0,
                }
                for p in self.players
            ],
            "state": self.state.to_public(hero_seat=hero_seat_local) if self.state else None,
            "legal_actions": legal,
            "last_coach": coach_feedback.to_dict() if coach_feedback else (
                self.last_coach.to_dict() if self.last_coach else None
            ),
            "events_tail": self.events[-30:],
            "hand_complete": self.state.street.value == "complete" if self.state else False,
            "tournament_over": len(alive) <= 1,
            "ranking_when_busted": [
                {"seat": p.seat, "name": p.name} for p in self.players if p.stack == 0
            ],
        }


# ---- registry ----
SESSIONS: dict[str, TournamentSession] = {}


def create_session(config: TournamentConfig) -> TournamentSession:
    session = TournamentSession(config)
    SESSIONS[session.id] = session
    return session


def get_session(session_id: str) -> TournamentSession:
    if session_id not in SESSIONS:
        raise KeyError(f"Session {session_id} not found")
    return SESSIONS[session_id]
