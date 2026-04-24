"""AI bot profiles for tournament training.

Each profile decides actions using a mix of:
  - preflop charts (a wider/tighter subset of the GTO chart)
  - postflop heuristics tuned to the profile's playstyle
  - bluff/value frequencies parameterized by `aggression`

Profiles available:
  - nit            tight-passive: only premium hands, rarely bluffs
  - rock           tight-passive but stickier OOP
  - tag            tight-aggressive (solid reg)
  - lag            loose-aggressive (high VPIP/PFR, high aggression)
  - fish           loose-passive recreational
  - maniac         extremely aggressive, bluffy
  - gto            approximation of pre-solved chart + balanced postflop
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..coach.charts import RFI_RANGES, VS_RFI
from ..poker.cards import hole_card_combo
from ..poker.equity import equity_vs_random
from ..poker.evaluator import category_of, evaluate_best
from ..poker.positions import position_label_6max
from ..poker.state import Action, ActionType, HandState, Street


@dataclass
class BotConfig:
    profile: str
    aggression: float  # 0..1: how often to bet/raise vs check/call when ambiguous
    bluff_freq: float  # 0..1: extra bluff frequency on light spots
    looseness: float  # 0..1: how much the chart range is widened
    skill: float  # 0..1: how often to make the GTO-correct decision


PROFILE_CONFIGS: dict[str, BotConfig] = {
    "nit": BotConfig("nit", aggression=0.25, bluff_freq=0.05, looseness=-0.30, skill=0.55),
    "rock": BotConfig("rock", aggression=0.30, bluff_freq=0.05, looseness=-0.25, skill=0.55),
    "tag": BotConfig("tag", aggression=0.55, bluff_freq=0.20, looseness=0.0, skill=0.85),
    "lag": BotConfig("lag", aggression=0.75, bluff_freq=0.40, looseness=0.20, skill=0.70),
    "fish": BotConfig("fish", aggression=0.30, bluff_freq=0.10, looseness=0.45, skill=0.30),
    "maniac": BotConfig("maniac", aggression=0.90, bluff_freq=0.55, looseness=0.30, skill=0.45),
    "gto": BotConfig("gto", aggression=0.6, bluff_freq=0.25, looseness=0.0, skill=0.95),
}


def _rfi_widened(position: str, looseness: float) -> set[str]:
    base = RFI_RANGES.get(position, set())
    if looseness >= 0:
        # Already covers most of the looser range — return as-is for tighter profiles
        return base
    # Tighter profile: drop weakest hands (heuristic: any 's' suited connector below 76s, weak Axo)
    drop = {h for h in base if (
        len(h) == 3 and h[2] == "o" and h[0] == "A" and h[1] in "23456789"
    ) or h in {"K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
                "Q4s", "Q5s", "Q6s", "Q7s", "Q8s",
                "98s", "87s", "76s", "65s", "54s", "43s", "32s",
                "T7s", "J7s", "J6s", "T6s", "32o", "43o", "54o", "65o"}}
    return base - drop


def _open_size(state: HandState, position: str) -> int:
    bb = state.big_blind
    if position in ("UTG", "HJ"):
        return int(bb * 2.2)
    if position == "SB":
        return int(bb * 3.0)
    return int(bb * 2.5)


def _three_bet_size(state: HandState, hero_pos: str) -> int:
    bb = state.big_blind
    if hero_pos in ("SB", "BB"):
        return int(bb * 11.0)
    return int(bb * 9.0)


def _preflop_decision(state: HandState, seat: int, cfg: BotConfig, rng: random.Random) -> Action:
    p = state.players[seat]
    legal = state.legal_actions(seat)
    actions = legal["actions"]
    pos = position_label_6max(seat, state.button_seat)
    combo = hole_card_combo(*p.cards)
    hist = [h for h in state.history if h["street"] == "preflop"]
    raisers = [h for h in hist if h["action"] and h["action"]["type"] in ("raise", "bet", "all_in")]

    # No prior raises: RFI decision
    if not raisers:
        rfi = _rfi_widened(pos, cfg.looseness)
        in_range = combo in rfi
        # Skill adjustment: if low skill, occasionally deviate
        if rng.random() > cfg.skill:
            in_range = not in_range
        if in_range and "raise" in actions:
            target = max(legal["min_raise_to"], _open_size(state, pos))
            target = min(target, legal["max_raise_to"])
            return Action(ActionType.RAISE, amount=target)
        if "check" in actions:
            return Action(ActionType.CHECK)
        return Action(ActionType.FOLD)

    # Single raise: decide 3bet/call/fold
    if len(raisers) == 1:
        open_seat = raisers[0]["seat"]
        open_pos = position_label_6max(open_seat, state.button_seat)
        chart = VS_RFI.get((pos, open_pos), {"3bet": set(), "call": set()})
        in_3b = combo in chart["3bet"]
        in_call = combo in chart["call"]
        # LAG/maniac: convert some calls to 3bets
        if cfg.profile in ("lag", "maniac") and in_call and rng.random() < cfg.aggression * 0.5:
            in_3b, in_call = True, False
        # Fish: convert some 3bets to calls
        if cfg.profile == "fish" and in_3b and rng.random() < 0.5:
            in_3b, in_call = False, True
        # Skill-based deviation
        if rng.random() > cfg.skill:
            in_3b = not in_3b if (in_3b or in_call) else False

        if in_3b and "raise" in actions:
            target = max(legal["min_raise_to"], _three_bet_size(state, pos))
            target = min(target, legal["max_raise_to"])
            return Action(ActionType.RAISE, amount=target)
        if in_call and "call" in actions and legal["to_call"] <= p.stack:
            return Action(ActionType.CALL, amount=legal["to_call"])
        if "check" in actions:
            return Action(ActionType.CHECK)
        return Action(ActionType.FOLD)

    # Multi-raise pots: tight 4bet with QQ+/AKs, else fold
    premium = combo in {"AA", "KK", "QQ", "AKs", "AKo"}
    if cfg.profile in ("lag", "maniac") and rng.random() < cfg.bluff_freq:
        premium = True  # 4bet bluff with garbage
    if premium and "raise" in actions:
        target = max(legal["min_raise_to"], state.current_bet * 2 + state.big_blind)
        target = min(target, legal["max_raise_to"])
        return Action(ActionType.RAISE, amount=target)
    if combo in {"JJ", "TT", "AQs", "AQo", "AJs"} and "call" in actions:
        return Action(ActionType.CALL, amount=legal["to_call"])
    return Action(ActionType.FOLD)


def _postflop_decision(state: HandState, seat: int, cfg: BotConfig, rng: random.Random) -> Action:
    p = state.players[seat]
    legal = state.legal_actions(seat)
    pot = state.pot
    to_call = legal["to_call"]
    score = evaluate_best([*p.cards, *state.board])
    cat = category_of(score)
    eq = equity_vs_random(p.cards, state.board, iters=200, rng=rng)

    bluff_roll = rng.random() < cfg.bluff_freq
    aggressive_roll = rng.random() < cfg.aggression

    # Facing a bet
    if to_call > 0:
        pot_odds = to_call / (pot + to_call)
        # Strong: raise for value (if possible) or call
        if cat >= 3 or eq > 0.70:
            if "raise" in legal["actions"] and aggressive_roll:
                target = min(legal["max_raise_to"], int(state.current_bet * 2.5))
                target = max(target, legal["min_raise_to"])
                return Action(ActionType.RAISE, amount=target)
            return Action(ActionType.CALL, amount=to_call)
        # Medium: call if equity > pot odds (with skill noise)
        if eq > pot_odds + 0.05:
            return Action(ActionType.CALL, amount=to_call)
        # Weak: occasional bluff-raise
        if "raise" in legal["actions"] and bluff_roll and cfg.profile in ("lag", "maniac"):
            target = min(legal["max_raise_to"], int(state.current_bet * 3))
            target = max(target, legal["min_raise_to"])
            return Action(ActionType.RAISE, amount=target)
        if "call" in legal["actions"] and cfg.profile == "fish" and rng.random() < 0.5:
            return Action(ActionType.CALL, amount=to_call)
        return Action(ActionType.FOLD)

    # No bet to face
    # Strong: bet for value
    if cat >= 2 or eq > 0.65:
        if "bet" in legal["actions"] and aggressive_roll:
            target = max(legal["min_raise_to"], int(pot * 0.66))
            target = min(target, legal["max_raise_to"])
            return Action(ActionType.RAISE if state.current_bet > 0 else ActionType.BET, amount=target)
    # Bluff
    if bluff_roll and "bet" in legal["actions"] and aggressive_roll:
        target = max(legal["min_raise_to"], int(pot * 0.50))
        target = min(target, legal["max_raise_to"])
        return Action(ActionType.RAISE if state.current_bet > 0 else ActionType.BET, amount=target)
    if "check" in legal["actions"]:
        return Action(ActionType.CHECK)
    return Action(ActionType.FOLD)


def decide(state: HandState, seat: int, profile: str, rng: random.Random | None = None) -> Action:
    cfg = PROFILE_CONFIGS.get(profile, PROFILE_CONFIGS["tag"])
    rng = rng or random.Random()
    if state.street == Street.PREFLOP:
        return _preflop_decision(state, seat, cfg, rng)
    return _postflop_decision(state, seat, cfg, rng)


PROFILE_LABELS = {
    "nit": "Nit (cực tight, ít bluff)",
    "rock": "Rock (tight-passive, hay station)",
    "tag": "TAG (tight-aggressive, reg solid)",
    "lag": "LAG (loose-aggressive, high IQ)",
    "fish": "Fish (recreational, calls quá nhiều)",
    "maniac": "Maniac (jam everything)",
    "gto": "GTO Bot (gần solver)",
}
