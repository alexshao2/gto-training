"""Smoke tests for the poker engine + coach."""
from __future__ import annotations

import random

from app.bots.profiles import decide
from app.coach.coach import evaluate_action
from app.poker.cards import Card, Deck, Rank, Suit, hole_card_combo
from app.poker.evaluator import (
    FLUSH,
    STRAIGHT,
    category_of,
    evaluate_5,
    evaluate_best,
)
from app.poker.state import Action, ActionType, HandState, Player, Street


def _c(s: str) -> Card:
    return Card.from_str(s)


def test_card_basics():
    c = Card(Rank.ACE, Suit.SPADES)
    assert str(c) == "As"
    assert Card.from_str("Td") == Card(Rank.TEN, Suit.DIAMONDS)


def test_deck_unique():
    d = Deck(rng=random.Random(42))
    cards = d.deal(52)
    assert len(set(cards)) == 52


def test_evaluator_flush_beats_straight():
    flush = [_c("Ah"), _c("Kh"), _c("9h"), _c("4h"), _c("2h")]
    straight = [_c("9c"), _c("8d"), _c("7s"), _c("6h"), _c("5c")]
    assert category_of(evaluate_5(flush)) == FLUSH
    assert category_of(evaluate_5(straight)) == STRAIGHT
    assert evaluate_5(flush) > evaluate_5(straight)


def test_evaluator_full_house_beats_flush():
    fh = [_c("Ah"), _c("Ad"), _c("As"), _c("Kc"), _c("Kd")]
    fl = [_c("Ah"), _c("Kh"), _c("9h"), _c("4h"), _c("2h")]
    assert evaluate_5(fh) > evaluate_5(fl)


def test_quads_beats_full_house():
    q = [_c("9h"), _c("9d"), _c("9c"), _c("9s"), _c("Ah")]
    fh = [_c("Ah"), _c("Ad"), _c("As"), _c("Kc"), _c("Kd")]
    assert evaluate_5(q) > evaluate_5(fh)


def test_evaluate_best_7_cards():
    cards = [_c("Ah"), _c("Kh"), _c("Qh"), _c("Jh"), _c("Th"), _c("2c"), _c("3d")]
    score = evaluate_best(cards)
    # Royal flush
    assert category_of(score) == 8


def test_combo_string():
    assert hole_card_combo(_c("Ah"), _c("Kh")) == "AKs"
    assert hole_card_combo(_c("Ah"), _c("Kd")) == "AKo"
    assert hole_card_combo(_c("9c"), _c("9d")) == "99"


def test_full_hand_runs_to_completion():
    players = [
        Player(seat=0, name="Hero", stack=10000, is_human=True, profile="human"),
        Player(seat=1, name="B1", stack=10000, profile="tag"),
        Player(seat=2, name="B2", stack=10000, profile="lag"),
        Player(seat=3, name="B3", stack=10000, profile="fish"),
        Player(seat=4, name="B4", stack=10000, profile="nit"),
        Player(seat=5, name="B5", stack=10000, profile="gto"),
    ]
    rng = random.Random(7)
    state = HandState.new_hand(
        players=players, button_seat=0, small_blind=50, big_blind=100, ante=10, rng=rng
    )
    # Hero auto-folds, bots play
    safety = 200
    while state.street not in (Street.SHOWDOWN, Street.COMPLETE) and safety > 0:
        seat = state.to_act_seat
        p = state.players[seat]
        if p.is_human:
            state.apply_action(seat, Action(ActionType.FOLD))
            continue
        action = decide(state, seat, p.profile, rng)
        try:
            state.apply_action(seat, action)
        except ValueError:
            legal = state.legal_actions(seat)
            if "check" in legal["actions"]:
                state.apply_action(seat, Action(ActionType.CHECK))
            else:
                state.apply_action(seat, Action(ActionType.FOLD))
        safety -= 1
    assert state.street == Street.COMPLETE
    assert sum(p.stack for p in players) > 50000  # chips conserved-ish (with antes)


def test_coach_flags_premium_fold_preflop():
    players = [
        Player(seat=0, name="Hero", stack=10000, is_human=True, profile="human"),
        Player(seat=1, name="B1", stack=10000, profile="tag"),
        Player(seat=2, name="B2", stack=10000, profile="tag"),
        Player(seat=3, name="B3", stack=10000, profile="tag"),
        Player(seat=4, name="B4", stack=10000, profile="tag"),
        Player(seat=5, name="B5", stack=10000, profile="tag"),
    ]
    state = HandState.new_hand(
        players=players, button_seat=3, small_blind=50, big_blind=100,
        rng=random.Random(0),
    )
    # Force hero to hold AA on BTN (seat 3 is BTN) — actually seat 0
    # Hero is seat 0; with button=3, seat 0 = (0-3)%6 = 3 => UTG
    state.players[0].cards = (_c("As"), _c("Ah"))
    fb = evaluate_action(state, 0, Action(ActionType.FOLD))
    assert fb.is_mistake
    assert fb.severity in ("major", "blunder")
