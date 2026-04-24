"""Quick simulation: run N hands with hero set to auto-fold, count what
fraction reach flop / turn / river / showdown, and how many are uncontested
(i.e. ended preflop because everyone but one player folded).

Usage:
    cd backend && python -m scripts.smoke_streets [N=200]
"""
from __future__ import annotations

import random
import sys
from collections import Counter

from app.bots.profiles import decide
from app.poker.state import (
    Action,
    ActionType,
    HandState,
    Player,
    Street,
)

PROFILES = ["tag", "lag", "fish", "nit", "gto", "rock"]


def run_hand(rng: random.Random) -> tuple[str, bool]:
    """Returns (street_reached, was_uncontested_preflop).

    `street_reached` is the most-advanced street with at least 2 active players.
    """
    players = [
        Player(seat=i, name=f"P{i}", stack=10_000, is_human=False, profile=PROFILES[i % len(PROFILES)])
        for i in range(6)
    ]
    state = HandState.new_hand(players=players, button_seat=0, small_blind=50, big_blind=100, ante=0, rng=rng)

    most_advanced = state.street.value
    street_at_action: list[str] = []
    safety = 0
    while state.street not in (Street.SHOWDOWN, Street.COMPLETE) and safety < 400:
        seat = state.to_act_seat
        if seat is None:
            break
        p = state.players[seat]
        if p.folded or p.all_in:
            # Should not happen with engine; bail
            break
        action = decide(state, seat, p.profile, rng)
        try:
            state.apply_action(seat, action)
        except ValueError:
            legal = state.legal_actions(seat)
            if "check" in legal["actions"]:
                state.apply_action(seat, Action(ActionType.CHECK))
            else:
                state.apply_action(seat, Action(ActionType.FOLD))
        street_at_action.append(state.street.value)
        if state.street.value not in ("showdown", "complete"):
            most_advanced = state.street.value
        safety += 1

    final_street = state.street.value
    if final_street == "complete":
        # If there were multiple active players at completion -> reached showdown
        active = [p for p in state.players if not p.folded]
        if len(active) >= 2:
            most_advanced = "showdown"
    elif final_street == "showdown":
        most_advanced = "showdown"

    # Was it uncontested preflop? (only one player remained while still on preflop)
    uncontested_pf = bool(state.winners) and any(
        w.get("reason") == "uncontested" for w in state.winners
    ) and "flop" not in [s for s in street_at_action]

    return most_advanced, uncontested_pf


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    rng = random.Random(42)
    counts: Counter = Counter()
    uncontested = 0
    for _ in range(n):
        st, unc = run_hand(rng)
        counts[st] += 1
        uncontested += int(unc)

    print(f"== {n} hands simulated ==")
    order = ["preflop", "flop", "turn", "river", "showdown"]
    for s in order:
        c = counts.get(s, 0)
        print(f"  {s:9s} reached: {c:3d} ({c / n:6.1%})")

    reached_flop = sum(counts[s] for s in ("flop", "turn", "river", "showdown"))
    reached_river = sum(counts[s] for s in ("river", "showdown"))
    reached_show = counts.get("showdown", 0)
    print()
    print(f"  any flop+: {reached_flop / n:6.1%}")
    print(f"  any river+: {reached_river / n:6.1%}")
    print(f"  showdown:  {reached_show / n:6.1%}")
    print(f"  uncontested preflop: {uncontested / n:6.1%}")


if __name__ == "__main__":
    main()
