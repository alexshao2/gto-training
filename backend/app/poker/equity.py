"""Monte-Carlo equity estimation: hero hand vs villain range / random hand."""
from __future__ import annotations

import random
from collections.abc import Iterable

from .cards import Card, Rank, Suit, all_cards
from .evaluator import evaluate_best


def _expand_combo(combo: str) -> list[tuple[Card, Card]]:
    """Expand 'AKs' / 'AKo' / 'AA' into list of concrete two-card combos."""
    out: list[tuple[Card, Card]] = []
    if len(combo) == 2 and combo[0] == combo[1]:
        r = Rank("23456789TJQKA".index(combo[0]) + 2)
        suits = list(Suit)
        for i in range(4):
            for j in range(i + 1, 4):
                out.append((Card(r, suits[i]), Card(r, suits[j])))
        return out
    if len(combo) != 3:
        raise ValueError(f"bad combo {combo}")
    hi = Rank("23456789TJQKA".index(combo[0]) + 2)
    lo = Rank("23456789TJQKA".index(combo[1]) + 2)
    suited = combo[2] == "s"
    if suited:
        for s in Suit:
            out.append((Card(hi, s), Card(lo, s)))
    else:
        for s1 in Suit:
            for s2 in Suit:
                if s1 != s2:
                    out.append((Card(hi, s1), Card(lo, s2)))
    return out


def expand_range(combos: Iterable[str]) -> list[tuple[Card, Card]]:
    out: list[tuple[Card, Card]] = []
    for c in combos:
        out.extend(_expand_combo(c))
    return out


def equity_vs_random(
    hero: tuple[Card, Card],
    board: list[Card] | None = None,
    iters: int = 400,
    rng: random.Random | None = None,
) -> float:
    rng = rng or random.Random()
    board = board or []
    used = set([*hero, *board])
    deck_pool = [c for c in all_cards() if c not in used]
    wins = ties = total = 0
    for _ in range(iters):
        sample = rng.sample(deck_pool, 2 + (5 - len(board)))
        villain = (sample[0], sample[1])
        run_board = board + sample[2:]
        h = evaluate_best([*hero, *run_board])
        v = evaluate_best([*villain, *run_board])
        total += 1
        if h > v:
            wins += 1
        elif h == v:
            ties += 1
    return (wins + ties / 2) / max(total, 1)


def equity_vs_range(
    hero: tuple[Card, Card],
    villain_combos: list[str],
    board: list[Card] | None = None,
    iters: int = 400,
    rng: random.Random | None = None,
) -> float:
    rng = rng or random.Random()
    board = board or []
    villain_pool = expand_range(villain_combos)
    used_hero = set([*hero, *board])
    villain_pool = [
        v for v in villain_pool if v[0] not in used_hero and v[1] not in used_hero
    ]
    if not villain_pool:
        return equity_vs_random(hero, board, iters, rng)
    wins = ties = total = 0
    for _ in range(iters):
        v = rng.choice(villain_pool)
        used = set([*hero, *board, *v])
        remaining = [c for c in all_cards() if c not in used]
        runout = rng.sample(remaining, 5 - len(board))
        run_board = board + runout
        hs = evaluate_best([*hero, *run_board])
        vs_ = evaluate_best([*v, *run_board])
        total += 1
        if hs > vs_:
            wins += 1
        elif hs == vs_:
            ties += 1
    return (wins + ties / 2) / max(total, 1)
