"""Position helpers for 6-max NLHE."""
from __future__ import annotations


def position_label_6max(seat: int, button_seat: int) -> str:
    """Map a seat number to its position label given the button location.

    6-max order: BTN, SB, BB, UTG, MP (HJ), CO. Order is *clockwise* from BTN.
    """
    offset = (seat - button_seat) % 6
    return ["BTN", "SB", "BB", "UTG", "HJ", "CO"][offset]


PREFLOP_OPEN_ORDER = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
