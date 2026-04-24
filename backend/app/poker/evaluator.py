"""5-/7-card hand evaluator for Texas Hold'em.

Returns a single integer score: higher = better. Encoded as
  category * 10**10 + tiebreaker_value
so any two ranks can be compared with `>`/`<`/`==`.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from itertools import combinations

from .cards import Card

# Hand category constants (higher is stronger)
HIGH_CARD = 0
ONE_PAIR = 1
TWO_PAIR = 2
THREE_KIND = 3
STRAIGHT = 4
FLUSH = 5
FULL_HOUSE = 6
FOUR_KIND = 7
STRAIGHT_FLUSH = 8

CATEGORY_NAMES = {
    HIGH_CARD: "High Card",
    ONE_PAIR: "One Pair",
    TWO_PAIR: "Two Pair",
    THREE_KIND: "Three of a Kind",
    STRAIGHT: "Straight",
    FLUSH: "Flush",
    FULL_HOUSE: "Full House",
    FOUR_KIND: "Four of a Kind",
    STRAIGHT_FLUSH: "Straight Flush",
}


def _kicker_value(ranks: list[int]) -> int:
    """Pack up to 5 rank ints (2..14) into a single int for tiebreak."""
    v = 0
    for r in ranks[:5]:
        v = v * 16 + r
    return v


def _is_straight(ranks_sorted_desc: list[int]) -> int | None:
    """Given unique sorted-desc ranks, return top rank of straight or None."""
    rs = sorted(set(ranks_sorted_desc), reverse=True)
    # Wheel: A-2-3-4-5
    if {14, 2, 3, 4, 5}.issubset(set(rs)):
        wheel_top = 5
    else:
        wheel_top = None
    for i in range(len(rs) - 4):
        window = rs[i : i + 5]
        if window[0] - window[4] == 4 and len(set(window)) == 5:
            return window[0]
    return wheel_top


def evaluate_5(cards: list[Card]) -> int:
    if len(cards) != 5:
        raise ValueError("evaluate_5 needs exactly 5 cards")
    ranks = sorted([c.rank.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    rank_counts = Counter(ranks)
    counts_by_rank = sorted(rank_counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    pattern = tuple(c for _, c in counts_by_rank)

    is_flush = len(set(suits)) == 1
    straight_top = _is_straight(ranks)

    if is_flush and straight_top:
        return STRAIGHT_FLUSH * 10**10 + straight_top
    if pattern[0] == 4:
        quad = counts_by_rank[0][0]
        kicker = counts_by_rank[1][0]
        return FOUR_KIND * 10**10 + _kicker_value([quad, kicker])
    if pattern[0] == 3 and pattern[1] >= 2:
        trip = counts_by_rank[0][0]
        pair = counts_by_rank[1][0]
        return FULL_HOUSE * 10**10 + _kicker_value([trip, pair])
    if is_flush:
        return FLUSH * 10**10 + _kicker_value(ranks)
    if straight_top:
        return STRAIGHT * 10**10 + straight_top
    if pattern[0] == 3:
        trip = counts_by_rank[0][0]
        kickers = sorted([r for r in ranks if r != trip], reverse=True)
        return THREE_KIND * 10**10 + _kicker_value([trip] + kickers)
    if pattern[0] == 2 and pattern[1] == 2:
        pair_hi = max(counts_by_rank[0][0], counts_by_rank[1][0])
        pair_lo = min(counts_by_rank[0][0], counts_by_rank[1][0])
        kicker = max(r for r in ranks if r != pair_hi and r != pair_lo)
        return TWO_PAIR * 10**10 + _kicker_value([pair_hi, pair_lo, kicker])
    if pattern[0] == 2:
        pair = counts_by_rank[0][0]
        kickers = sorted([r for r in ranks if r != pair], reverse=True)
        return ONE_PAIR * 10**10 + _kicker_value([pair] + kickers)
    return HIGH_CARD * 10**10 + _kicker_value(ranks)


def evaluate_best(cards: Iterable[Card]) -> int:
    cards = list(cards)
    if len(cards) < 5:
        raise ValueError("Need at least 5 cards")
    if len(cards) == 5:
        return evaluate_5(cards)
    return max(evaluate_5(list(combo)) for combo in combinations(cards, 5))


def category_of(score: int) -> int:
    return score // 10**10


def category_name(score: int) -> str:
    return CATEGORY_NAMES[category_of(score)]
