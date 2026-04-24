"""No-Limit Hold'em game state machine for a single hand at a 6-max table.

Pure-Python, deterministic given a seeded Deck. Designed for easy serialization
to the frontend and for AI bots / GTO coach to reason about.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from .cards import Card, Deck


class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    COMPLETE = "complete"


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


# 6-max position labels, index = seat offset from button (0 = button)
POSITIONS_6 = ["BTN", "SB", "BB", "UTG", "MP", "CO"]


@dataclass
class Player:
    seat: int  # 0..N-1
    name: str
    stack: int  # remaining behind, in chips
    is_human: bool = False
    profile: str = "tag"  # bot profile id when not human
    cards: tuple[Card, Card] | None = None
    bet_this_street: int = 0
    total_invested: int = 0
    folded: bool = False
    all_in: bool = False
    last_action: Action | None = None

    def to_public(self, *, reveal: bool = False) -> dict:
        return {
            "seat": self.seat,
            "name": self.name,
            "stack": self.stack,
            "is_human": self.is_human,
            "profile": self.profile,
            "cards": [str(c) for c in self.cards] if (self.cards and reveal) else None,
            "bet_this_street": self.bet_this_street,
            "total_invested": self.total_invested,
            "folded": self.folded,
            "all_in": self.all_in,
            "last_action": self.last_action.to_dict() if self.last_action else None,
        }


@dataclass
class Action:
    type: ActionType
    amount: int = 0  # for BET/RAISE/CALL: total chips put in this action

    def to_dict(self) -> dict:
        return {"type": self.type.value, "amount": self.amount}


@dataclass
class HandState:
    """Encapsulates the state of one hand from preflop to showdown."""

    players: list[Player]
    button_seat: int
    small_blind: int
    big_blind: int
    ante: int = 0
    deck: Deck = field(default_factory=Deck)
    board: list[Card] = field(default_factory=list)
    pot: int = 0
    street: Street = Street.PREFLOP
    current_bet: int = 0  # the highest bet on the current street
    last_raise_size: int = 0  # for min-raise rule
    to_act_seat: int = 0
    last_aggressor_seat: int | None = None
    history: list[dict] = field(default_factory=list)  # serialized actions
    winners: list[dict] = field(default_factory=list)
    showdown_revealed: bool = False

    # ---------------- setup ----------------
    @classmethod
    def new_hand(
        cls,
        players: list[Player],
        button_seat: int,
        small_blind: int,
        big_blind: int,
        ante: int = 0,
        rng: random.Random | None = None,
    ) -> HandState:
        for p in players:
            p.cards = None
            p.bet_this_street = 0
            p.total_invested = 0
            p.folded = False
            p.all_in = False
            p.last_action = None
        deck = Deck(rng=rng)
        st = cls(
            players=players,
            button_seat=button_seat,
            small_blind=small_blind,
            big_blind=big_blind,
            ante=ante,
            deck=deck,
        )
        st._post_blinds_and_deal()
        return st

    def _seat_order_from(self, start_seat: int) -> list[int]:
        n = len(self.players)
        return [(start_seat + i) % n for i in range(n)]

    def active_players(self) -> list[Player]:
        return [p for p in self.players if not p.folded]

    def players_can_act(self) -> list[Player]:
        return [p for p in self.players if not p.folded and not p.all_in]

    def _post_blinds_and_deal(self) -> None:
        n = len(self.players)
        # Ante
        if self.ante > 0:
            for p in self.players:
                pay = min(self.ante, p.stack)
                p.stack -= pay
                p.total_invested += pay
                self.pot += pay
                if p.stack == 0:
                    p.all_in = True
        # Blinds
        if n == 2:
            sb_seat = self.button_seat
            bb_seat = (self.button_seat + 1) % n
            first_to_act = sb_seat
        else:
            sb_seat = (self.button_seat + 1) % n
            bb_seat = (self.button_seat + 2) % n
            first_to_act = (self.button_seat + 3) % n
        self._post_blind(sb_seat, self.small_blind)
        self._post_blind(bb_seat, self.big_blind)
        self.current_bet = self.big_blind
        self.last_raise_size = self.big_blind
        # Deal 2 cards to each player, in standard order
        order = self._seat_order_from((self.button_seat + 1) % n)
        for _ in range(2):
            for seat in order:
                self.players[seat].cards = self.players[seat].cards  # placeholder
        # Deal proper
        for seat in order:
            cards = self.deck.deal(2)
            self.players[seat].cards = (cards[0], cards[1])
        self.to_act_seat = first_to_act
        self.last_aggressor_seat = bb_seat
        self.street = Street.PREFLOP

    def _post_blind(self, seat: int, amount: int) -> None:
        p = self.players[seat]
        pay = min(amount, p.stack)
        p.stack -= pay
        p.bet_this_street += pay
        p.total_invested += pay
        self.pot += pay
        if p.stack == 0:
            p.all_in = True

    # ---------------- action helpers ----------------
    def legal_actions(self, seat: int) -> dict:
        """Return dict describing what `seat` can legally do right now."""
        p = self.players[seat]
        if p.folded or p.all_in:
            return {"actions": []}
        to_call = max(0, self.current_bet - p.bet_this_street)
        actions: list[str] = []
        if to_call > 0:
            actions.append(ActionType.FOLD.value)
            actions.append(ActionType.CALL.value)
        else:
            actions.append(ActionType.CHECK.value)
        # bet/raise
        min_raise_to = self.current_bet + self.last_raise_size
        max_raise_to = p.bet_this_street + p.stack  # all-in
        if max_raise_to > self.current_bet:
            if self.current_bet == 0:
                actions.append(ActionType.BET.value)
            else:
                actions.append(ActionType.RAISE.value)
        return {
            "actions": actions,
            "to_call": to_call,
            "min_raise_to": min(min_raise_to, max_raise_to),
            "max_raise_to": max_raise_to,
            "pot": self.pot,
            "current_bet": self.current_bet,
            "stack": p.stack,
        }

    # ---------------- apply action ----------------
    def apply_action(self, seat: int, action: Action) -> None:
        if seat != self.to_act_seat:
            raise ValueError(f"Not seat {seat}'s turn (to act: {self.to_act_seat})")
        p = self.players[seat]
        if p.folded or p.all_in:
            raise ValueError("Player cannot act")

        if action.type == ActionType.FOLD:
            p.folded = True
            p.last_action = action
        elif action.type == ActionType.CHECK:
            if self.current_bet > p.bet_this_street:
                raise ValueError("Cannot check facing a bet")
            p.last_action = action
        elif action.type == ActionType.CALL:
            to_call = self.current_bet - p.bet_this_street
            pay = min(to_call, p.stack)
            p.stack -= pay
            p.bet_this_street += pay
            p.total_invested += pay
            self.pot += pay
            if p.stack == 0:
                p.all_in = True
            p.last_action = Action(ActionType.CALL, amount=pay)
        elif action.type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            target = action.amount  # interpreted as "raise to"
            if target > p.bet_this_street + p.stack:
                target = p.bet_this_street + p.stack  # cap at all-in
            increment = target - p.bet_this_street
            if increment <= 0:
                raise ValueError("Raise amount must be positive")
            # Min raise check (allow all-in shorts)
            min_raise_to = self.current_bet + self.last_raise_size
            is_all_in = (p.stack == increment)
            if target < min_raise_to and not is_all_in:
                raise ValueError(
                    f"Raise too small; min raise to {min_raise_to}, got {target}"
                )
            p.stack -= increment
            p.bet_this_street += increment
            p.total_invested += increment
            self.pot += increment
            raise_size = target - self.current_bet
            if raise_size >= self.last_raise_size:
                self.last_raise_size = raise_size
                self.last_aggressor_seat = seat
            self.current_bet = max(self.current_bet, target)
            if p.stack == 0:
                p.all_in = True
            p.last_action = Action(ActionType.RAISE, amount=target)
        else:
            raise ValueError(f"Unknown action {action.type}")

        self.history.append(
            {
                "street": self.street.value,
                "seat": seat,
                "action": p.last_action.to_dict() if p.last_action else None,
            }
        )

        self._advance_turn()

    # ---------------- turn / street advancement ----------------
    def _advance_turn(self) -> None:
        # If only 1 player left -> hand ends
        if len(self.active_players()) == 1:
            self.street = Street.COMPLETE
            self._award_pot_uncontested()
            return

        # Find next player who can act
        n = len(self.players)
        next_seat = (self.to_act_seat + 1) % n
        for _ in range(n):
            pl = self.players[next_seat]
            if not pl.folded and not pl.all_in:
                # Has the betting round closed?
                if self._betting_round_closed(next_seat):
                    self._end_street()
                    return
                self.to_act_seat = next_seat
                return
            next_seat = (next_seat + 1) % n

        # Everyone all-in or no one can act
        self._end_street()

    def _betting_round_closed(self, next_seat: int) -> bool:
        active = [p for p in self.players if not p.folded and not p.all_in]
        if len(active) <= 1:
            return True
        # All active players have matched the current bet
        all_matched = all(p.bet_this_street == self.current_bet for p in active)
        if not all_matched:
            return False
        # Action has come back around to last aggressor (or BB preflop with no raise)
        if self.last_aggressor_seat is None:
            return True
        if next_seat == self.last_aggressor_seat:
            return True
        return False

    def _end_street(self) -> None:
        # Reset per-street bets
        for p in self.players:
            p.bet_this_street = 0
        self.current_bet = 0
        self.last_raise_size = self.big_blind
        self.last_aggressor_seat = None

        # Deal next street
        if self.street == Street.PREFLOP:
            self.deck.deal(1)  # burn
            self.board.extend(self.deck.deal(3))
            self.street = Street.FLOP
        elif self.street == Street.FLOP:
            self.deck.deal(1)
            self.board.extend(self.deck.deal(1))
            self.street = Street.TURN
        elif self.street == Street.TURN:
            self.deck.deal(1)
            self.board.extend(self.deck.deal(1))
            self.street = Street.RIVER
        elif self.street == Street.RIVER:
            self.street = Street.SHOWDOWN
            self._showdown()
            return
        else:
            self.street = Street.COMPLETE
            return

        # If <=1 can still act (rest all-in), run it out and go to showdown
        if len(self.players_can_act()) <= 1 and len(self.active_players()) > 1:
            # Deal remaining streets quickly
            self._end_street()
            return

        # Determine first to act for postflop: first active player after button
        n = len(self.players)
        seat = (self.button_seat + 1) % n
        for _ in range(n):
            p = self.players[seat]
            if not p.folded and not p.all_in:
                self.to_act_seat = seat
                return
            seat = (seat + 1) % n
        self._end_street()

    # ---------------- pot resolution ----------------
    def _award_pot_uncontested(self) -> None:
        winner = self.active_players()[0]
        winner.stack += self.pot
        self.winners = [
            {"seat": winner.seat, "amount": self.pot, "reason": "uncontested"}
        ]
        self.pot = 0
        self.street = Street.COMPLETE

    def _showdown(self) -> None:
        from .evaluator import category_name, evaluate_best

        contenders = self.active_players()
        self.showdown_revealed = True

        # Build side pots based on total_invested
        invests = sorted({p.total_invested for p in self.players if p.total_invested > 0})
        prev = 0
        side_pots: list[tuple[int, list[Player]]] = []
        for level in invests:
            eligible = [p for p in contenders if p.total_invested >= level]
            contributors = [p for p in self.players if p.total_invested >= level]
            slice_size = (level - prev) * len(contributors)
            if slice_size > 0 and eligible:
                side_pots.append((slice_size, eligible))
            prev = level

        # Award each side pot
        for amount, eligible in side_pots:
            scores = [(evaluate_best([*p.cards, *self.board]), p) for p in eligible]
            best = max(s for s, _ in scores)
            winners = [p for s, p in scores if s == best]
            split = amount // len(winners)
            remainder = amount - split * len(winners)
            for w in winners:
                w.stack += split
            # Give odd chip to first winner left of button
            if remainder > 0 and winners:
                winners[0].stack += remainder
            for w in winners:
                self.winners.append(
                    {
                        "seat": w.seat,
                        "amount": split + (remainder if w is winners[0] else 0),
                        "reason": category_name(
                            evaluate_best([*w.cards, *self.board])
                        ),
                    }
                )
        self.pot = 0
        self.street = Street.COMPLETE

    # ---------------- serialization ----------------
    def to_public(self, hero_seat: int | None = None) -> dict:
        reveal_all = self.showdown_revealed or self.street == Street.COMPLETE
        return {
            "street": self.street.value,
            "board": [str(c) for c in self.board],
            "pot": self.pot,
            "current_bet": self.current_bet,
            "to_act_seat": self.to_act_seat if self.street not in (Street.SHOWDOWN, Street.COMPLETE) else None,
            "button_seat": self.button_seat,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "ante": self.ante,
            "players": [
                p.to_public(reveal=(reveal_all or p.seat == hero_seat))
                for p in self.players
            ],
            "history": self.history,
            "winners": self.winners,
        }
