"""Tournament blind structures + ICM helper."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    sb: int
    bb: int
    ante: int
    minutes: int


# Turbo MTT structure (standard online turbo)
TURBO_STRUCTURE: list[Level] = [
    Level(10, 20, 0, 5),
    Level(15, 30, 0, 5),
    Level(25, 50, 5, 5),
    Level(50, 100, 10, 5),
    Level(75, 150, 20, 5),
    Level(100, 200, 25, 5),
    Level(150, 300, 40, 5),
    Level(200, 400, 50, 5),
    Level(300, 600, 75, 5),
    Level(400, 800, 100, 5),
    Level(600, 1200, 150, 5),
    Level(800, 1600, 200, 5),
    Level(1200, 2400, 300, 5),
    Level(1500, 3000, 400, 5),
    Level(2000, 4000, 500, 5),
    Level(3000, 6000, 750, 5),
]

# Regular MTT (slower)
REGULAR_STRUCTURE: list[Level] = [
    Level(10, 20, 0, 12),
    Level(15, 30, 0, 12),
    Level(25, 50, 5, 12),
    Level(50, 100, 10, 12),
    Level(75, 150, 15, 12),
    Level(100, 200, 25, 12),
    Level(150, 300, 40, 12),
    Level(200, 400, 50, 12),
    Level(300, 600, 75, 12),
    Level(400, 800, 100, 12),
    Level(500, 1000, 125, 12),
    Level(750, 1500, 150, 12),
    Level(1000, 2000, 200, 12),
    Level(1500, 3000, 400, 12),
    Level(2000, 4000, 500, 12),
    Level(3000, 6000, 750, 12),
    Level(5000, 10000, 1000, 12),
]

STRUCTURES = {
    "turbo": TURBO_STRUCTURE,
    "regular": REGULAR_STRUCTURE,
}


def icm_chip_chop(stacks: list[int], payouts: list[float]) -> list[float]:
    """Compute ICM equity for each player given chip stacks and payout structure.

    Uses the Malmuth-Harville model. `payouts` are the prize payouts in order
    (1st, 2nd, ...). Returns each player's expected payout.
    """
    n = len(stacks)
    # Pad payouts with zeros if fewer than players
    pays = list(payouts) + [0.0] * (n - len(payouts))
    pays = pays[:n]

    return _icm_iterative(stacks, pays)


def _icm_iterative(stacks: list[int], payouts: list[float]) -> list[float]:
    """Wrapper preserved for backwards-compatibility; delegates to closed form."""
    return _icm_recursive_closed(stacks, payouts)


def stack_eq_recurse(remaining: list[int], place: int, out: list[float], payouts: list[float], n: int) -> None:
    if place >= n or place >= len(payouts):
        return
    total = sum(remaining)
    if total <= 0:
        return
    pay = payouts[place]
    for i, s in enumerate(remaining):
        if s <= 0:
            continue
        p = s / total
        out[i] += p * pay
        sub = list(remaining)
        sub[i] = 0
        if sum(sub) > 0 and place + 1 < n and place + 1 < len(payouts):
            sub_eq = [0.0] * n
            stack_eq_recurse(sub, place + 1, sub_eq, payouts, n)
            for j in range(n):
                out[j] += p * sub_eq[j]


def _icm_recursive_closed(stacks: list[int], payouts: list[float]) -> list[float]:
    n = len(stacks)
    out = [0.0] * n
    # Pad payouts with zeros so we never index out of range
    padded = list(payouts) + [0.0] * max(0, n - len(payouts))
    stack_eq_recurse(stacks, 0, out, padded, n)
    return out
