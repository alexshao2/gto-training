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
    # Wider than baseline so multi-way pots reach the flop / turn / river
    # often — this is what the user wants to see for training.
    "nit": BotConfig("nit", aggression=0.30, bluff_freq=0.08, looseness=-0.10, skill=0.60),
    "rock": BotConfig("rock", aggression=0.30, bluff_freq=0.08, looseness=0.0, skill=0.55),
    "tag": BotConfig("tag", aggression=0.55, bluff_freq=0.22, looseness=0.10, skill=0.80),
    "lag": BotConfig("lag", aggression=0.75, bluff_freq=0.42, looseness=0.45, skill=0.70),
    "fish": BotConfig("fish", aggression=0.30, bluff_freq=0.10, looseness=0.75, skill=0.30),
    "maniac": BotConfig("maniac", aggression=0.90, bluff_freq=0.55, looseness=0.55, skill=0.45),
    "gto": BotConfig("gto", aggression=0.6, bluff_freq=0.25, looseness=0.10, skill=0.92),
}


# Hands to ADD on top of base RFI for loose profiles (suited connectors,
# suited gappers, weak Ax, broadway offsuit). Helps create multi-way pots.
_LOOSE_ADDITIONS: list[str] = [
    "K9o", "K8o", "Q8o", "J9o", "T8o", "97o", "86o", "75o",
    "K4s", "K3s", "K2s", "Q4s", "Q5s", "Q6s", "Q7s",
    "J6s", "J5s", "T5s", "T6s", "96s", "85s", "74s", "64s",
    "53s", "42s",
]


def _rfi_widened(position: str, looseness: float) -> set[str]:
    """Adjust RFI by `looseness` (>0 wider, <0 tighter)."""
    base = set(RFI_RANGES.get(position, set()))
    if looseness < 0:
        drop = {h for h in base if (
            len(h) == 3 and h[2] == "o" and h[0] == "A" and h[1] in "23456789"
        ) or h in {"K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
                    "Q4s", "Q5s", "Q6s", "Q7s", "Q8s",
                    "98s", "87s", "76s", "65s", "54s", "43s", "32s",
                    "T7s", "J7s", "J6s", "T6s", "32o", "43o", "54o", "65o"}}
        # Tightness scales: -0.3 drops a lot, -0.1 drops only worst
        n_drop = int(len(drop) * min(1.0, abs(looseness) * 3.0))
        drop_sorted = sorted(drop)
        return base - set(drop_sorted[:n_drop])
    if looseness > 0:
        # Add weak suited / suited gappers / loose offsuit broadways
        n_add = int(len(_LOOSE_ADDITIONS) * min(1.0, looseness * 1.5))
        return base | set(_LOOSE_ADDITIONS[:n_add])
    return base


# Generic vs-RFI defending ranges used when a specific (pos, open_pos)
# combo is not present in VS_RFI. Tight by default; widened by looseness.
_FALLBACK_3BET = {
    "AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs", "A5s", "A4s",
}
_FALLBACK_CALL_TIGHT = {
    "TT", "99", "88", "77", "66", "55", "44",
    "AQs", "AJs", "ATs", "A9s", "KQs", "KJs", "KTs",
    "QJs", "QTs", "JTs", "T9s", "98s", "87s", "76s", "65s",
    "AQo", "AJo", "KQo",
}
_FALLBACK_CALL_LOOSE_EXTRA = {
    "33", "22",
    "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
    "K9s", "K8s", "Q9s", "Q8s", "J9s", "J8s", "T8s", "97s", "86s", "75s", "54s",
    "ATo", "KJo", "KTo", "QJo", "QTo", "JTo",
}


_PREMIUM_HANDS = {
    "AA", "KK", "QQ", "JJ", "TT", "99", "88",
    "AKs", "AKo", "AQs", "AQo", "AJs", "ATs",
    "KQs", "KQo", "KJs",
}


def _is_marginally_playable(combo: str) -> bool:
    """Return True if the combo is plausibly defendable for a loose recreational
    player (any pair, any suited two-card, any two-card with broadway, any Ax).
    Used by fish/lag/maniac to widen their calling range vs a single raise.
    """
    # Pair
    if len(combo) == 2 and combo[0] == combo[1]:
        return True
    if len(combo) != 3:
        return False
    a, b, kind = combo[0], combo[1], combo[2]
    # Any Ax
    if a == "A":
        return True
    # Any suited
    if kind == "s":
        return True
    # Two broadway cards (T+) offsuit
    bw = set("TJQKA")
    if a in bw and b in bw:
        return True
    # Connected offsuit broadway-ish (e.g. T9o, 98o)
    rank_order = "23456789TJQKA"
    if a in rank_order and b in rank_order:
        gap = abs(rank_order.index(a) - rank_order.index(b))
        if gap <= 1 and rank_order.index(a) >= rank_order.index("9"):
            return True
    return False


def _fallback_defense_chart(hero_pos: str, open_pos: str, looseness: float) -> dict[str, set[str]]:
    """Best-effort defending chart for a (hero_pos, open_pos) pair not present
    in VS_RFI. Calls wider when in position vs out, and widens with `looseness`.
    """
    # Whether hero is in position vs the opener
    pf_order = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
    try:
        ip = pf_order.index(hero_pos) > pf_order.index(open_pos) and hero_pos not in ("SB", "BB")
    except ValueError:
        ip = False
    call = set(_FALLBACK_CALL_TIGHT)
    if looseness >= 0:
        # In position widens more, OOP narrows
        extra = _FALLBACK_CALL_LOOSE_EXTRA
        if ip:
            call |= extra
        else:
            # Take half (deterministic by sorted order)
            half = sorted(extra)[: len(extra) // 2]
            call |= set(half)
    return {"3bet": set(_FALLBACK_3BET), "call": call}


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
        is_premium = combo in _PREMIUM_HANDS
        # Skill adjustment only flips MARGINAL hands (premium always opens,
        # garbage rarely turns into an open). Skill is the chance to flip
        # a marginal decision in the wrong direction.
        if not is_premium and rng.random() > cfg.skill:
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
        chart = VS_RFI.get((pos, open_pos))
        if chart is None:
            chart = _fallback_defense_chart(pos, open_pos, cfg.looseness)
        in_3b = combo in chart["3bet"]
        in_call = combo in chart["call"]
        # LAG/maniac: convert some calls to 3bets
        if cfg.profile in ("lag", "maniac") and in_call and rng.random() < cfg.aggression * 0.5:
            in_3b, in_call = True, False
        # Fish: convert some 3bets to calls
        if cfg.profile == "fish" and in_3b and rng.random() < 0.5:
            in_3b, in_call = False, True
        # Looseness widening: fish / maniac / lag often call marginal hands
        # that aren't in the chart but look "playable" (any pair, suited, broadway).
        if not in_3b and not in_call and cfg.looseness > 0:
            playable = _is_marginally_playable(combo)
            # Probability scales with looseness; multi-way bonus for better odds.
            n_callers = len(
                [h for h in hist if h["action"] and h["action"]["type"] == "call"]
            )
            mult_bonus = min(0.25, n_callers * 0.10)
            if playable and rng.random() < cfg.looseness + mult_bonus:
                in_call = True
        # Skill-based deviation: low-skill bots sometimes downgrade a 3bet to a
        # call (passive mistake). We do NOT downgrade calls to folds — fish/loose
        # profiles overcall too much in real life, not the other way around.
        is_premium = combo in _PREMIUM_HANDS
        if not is_premium and rng.random() > cfg.skill:
            if in_3b:
                in_3b, in_call = False, True

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
    # Wider continue range vs 3-bet for fish / loose profiles (set-mining + sticky)
    set_mine = {"JJ", "TT", "99", "88", "77", "66", "55"}
    suited_continues = {"AQs", "AJs", "ATs", "KQs", "KJs"}
    bb_defend = {"AQo"}
    if combo in set_mine | suited_continues | bb_defend and "call" in actions:
        return Action(ActionType.CALL, amount=legal["to_call"])
    if cfg.profile == "fish" and "call" in actions and combo in {
        "44", "33", "22", "A9s", "A8s", "A7s", "KTs", "QJs", "QTs", "JTs", "AJo"
    }:
        return Action(ActionType.CALL, amount=legal["to_call"])
    return Action(ActionType.FOLD)


def _has_flush_draw(cards, board) -> bool:
    suits: dict[str, int] = {}
    for c in [*cards, *board]:
        suits[c.suit] = suits.get(c.suit, 0) + 1
    return any(v >= 4 for v in suits.values())


def _has_oesd(cards, board) -> bool:
    """Open-ended straight draw (4 to a straight, not gutshot)."""
    ranks = sorted({c.rank for c in [*cards, *board]})
    # 5-card windows
    rank_set = set(ranks)
    if {14, 2, 3, 4, 5} & rank_set == {2, 3, 4, 5}:
        return True
    for low in range(2, 11):
        window = {low, low + 1, low + 2, low + 3}
        if window.issubset(rank_set):
            return True
    return False


def _postflop_decision(state: HandState, seat: int, cfg: BotConfig, rng: random.Random) -> Action:
    p = state.players[seat]
    legal = state.legal_actions(seat)
    pot = max(state.pot, 1)
    to_call = legal["to_call"]
    score = evaluate_best([*p.cards, *state.board])
    cat = category_of(score)
    eq = equity_vs_random(p.cards, state.board, iters=240, rng=rng)

    has_fd = _has_flush_draw(p.cards, state.board) if state.board else False
    has_oesd = _has_oesd(p.cards, state.board) if state.board else False
    has_draw = has_fd or has_oesd

    # Pair+ (any pair counts as cat>=1 in our evaluator)
    has_pair = cat >= 1

    bluff_roll = rng.random() < cfg.bluff_freq
    aggressive_roll = rng.random() < cfg.aggression
    is_river = state.street == Street.RIVER

    # ---- Facing a bet ----
    if to_call > 0:
        pot_odds = to_call / (pot + to_call)
        bet_pct_pot = to_call / pot if pot > 0 else 1.0

        # Strong made hand (two pair+) → raise for value or call
        if cat >= 3 or eq > 0.72:
            if "raise" in legal["actions"] and aggressive_roll:
                target = min(legal["max_raise_to"], int(state.current_bet * 2.5))
                target = max(target, legal["min_raise_to"])
                return Action(ActionType.RAISE, amount=target)
            return Action(ActionType.CALL, amount=to_call)

        # Top/middle pair → mostly call, sometimes raise (TAG/LAG)
        if has_pair and eq >= 0.45:
            return Action(ActionType.CALL, amount=to_call)

        # Strong draw → call most of the time, sometimes semi-bluff raise
        if has_draw and not is_river:
            if (
                "raise" in legal["actions"]
                and cfg.profile in ("lag", "maniac", "tag")
                and rng.random() < cfg.bluff_freq * 0.8
            ):
                target = min(legal["max_raise_to"], int(state.current_bet * 2.7))
                target = max(target, legal["min_raise_to"])
                return Action(ActionType.RAISE, amount=target)
            return Action(ActionType.CALL, amount=to_call)

        # Decent equity vs pot odds → call (more lenient threshold for sticky profiles)
        equity_buffer = -0.03 if cfg.profile in ("fish", "lag", "maniac") else 0.04
        if eq > pot_odds + equity_buffer:
            return Action(ActionType.CALL, amount=to_call)

        # Fish: floats small bets a lot
        if cfg.profile == "fish" and bet_pct_pot < 0.55 and rng.random() < 0.55:
            return Action(ActionType.CALL, amount=to_call)

        # Bluff-raise (occasional)
        if (
            "raise" in legal["actions"]
            and bluff_roll
            and cfg.profile in ("lag", "maniac")
        ):
            target = min(legal["max_raise_to"], int(state.current_bet * 3))
            target = max(target, legal["min_raise_to"])
            return Action(ActionType.RAISE, amount=target)

        return Action(ActionType.FOLD)

    # ---- No bet to face (lead / cbet decision) ----
    # Strong made hand → value bet
    if cat >= 2 or eq > 0.65:
        if "bet" in legal["actions"] and aggressive_roll:
            target = max(legal["min_raise_to"], int(pot * 0.66))
            target = min(target, legal["max_raise_to"])
            return Action(
                ActionType.RAISE if state.current_bet > 0 else ActionType.BET,
                amount=target,
            )
        if "check" in legal["actions"]:
            return Action(ActionType.CHECK)

    # Pair: occasional thin value bet
    if has_pair and eq >= 0.55 and rng.random() < cfg.aggression * 0.5:
        if "bet" in legal["actions"]:
            target = max(legal["min_raise_to"], int(pot * 0.5))
            target = min(target, legal["max_raise_to"])
            return Action(
                ActionType.RAISE if state.current_bet > 0 else ActionType.BET,
                amount=target,
            )

    # Semi-bluff with a draw
    if has_draw and not is_river and bluff_roll and "bet" in legal["actions"]:
        target = max(legal["min_raise_to"], int(pot * 0.55))
        target = min(target, legal["max_raise_to"])
        return Action(
            ActionType.RAISE if state.current_bet > 0 else ActionType.BET,
            amount=target,
        )

    # Pure bluff (rare, only aggressive profiles)
    if (
        bluff_roll
        and aggressive_roll
        and "bet" in legal["actions"]
        and cfg.profile in ("lag", "maniac", "tag")
    ):
        target = max(legal["min_raise_to"], int(pot * 0.5))
        target = min(target, legal["max_raise_to"])
        return Action(
            ActionType.RAISE if state.current_bet > 0 else ActionType.BET,
            amount=target,
        )

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
