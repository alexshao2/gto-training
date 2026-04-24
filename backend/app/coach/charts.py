"""Pre-solved preflop GTO ranges for 6-max NLHE, 100bb effective stacks.

Frequencies are simplified percentages (0..1) representing how often a hand
should take a given action. These are based on commonly cited solver-derived
charts (e.g. GTO Wizard 100bb cash & similar tournament charts) and are not a
substitute for a real solver. They cover the most common scenarios:

  - RFI (raise first in)  by position
  - vs RFI: 3bet / call ranges by hero position vs villain position
  - vs 3bet: 4bet / call ranges
  - BB defense vs SB open / BTN open

Data is intentionally compact: each hand is mapped to a primary action plus
optional mixed strategy frequency. The coach evaluates the user's action
against these charts to flag deviations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal["fold", "call", "raise"]


@dataclass(frozen=True)
class ChartEntry:
    primary: Action
    raise_freq: float = 0.0  # for mixed: probability of raise
    call_freq: float = 0.0
    fold_freq: float = 0.0

    @property
    def is_pure(self) -> bool:
        return max(self.raise_freq, self.call_freq, self.fold_freq) >= 0.95


def _pure(action: Action) -> ChartEntry:
    return ChartEntry(
        primary=action,
        raise_freq=1.0 if action == "raise" else 0.0,
        call_freq=1.0 if action == "call" else 0.0,
        fold_freq=1.0 if action == "fold" else 0.0,
    )


# ---- RFI ranges: hand -> raise (else fold) ----
# Approximations of GTO Wizard 100bb cash 6-max RFI.
RFI_RANGES: dict[str, set[str]] = {
    "UTG": {
        "AA","KK","QQ","JJ","TT","99","88","77","66","55",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s","65s",
        "AKo","AQo","AJo","ATo","KQo",
    },
    "HJ": {
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","QJs","QTs","Q9s","Q8s","JTs","J9s","J8s",
        "T9s","T8s","98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o","KQo","KJo",
    },
    "CO": {
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s",
        "QJs","QTs","Q9s","Q8s","Q7s","JTs","J9s","J8s","J7s",
        "T9s","T8s","T7s","98s","97s","87s","86s","76s","75s","65s","54s","43s",
        "AKo","AQo","AJo","ATo","A9o","A8o","KQo","KJo","KTo","QJo","QTo","JTo",
    },
    "BTN": {
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
        "QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s","Q4s",
        "JTs","J9s","J8s","J7s","J6s","T9s","T8s","T7s","T6s",
        "98s","97s","96s","87s","86s","85s","76s","75s","74s","65s","64s","54s","53s","43s","32s",
        "AKo","AQo","AJo","ATo","A9o","A8o","A7o","A6o","A5o","A4o","A3o","A2o",
        "KQo","KJo","KTo","K9o","K8o","K7o",
        "QJo","QTo","Q9o","Q8o","JTo","J9o","J8o","T9o","T8o","98o","87o","76o",
    },
    "SB": {
        # SB raise-or-fold strategy (limps removed for simplicity)
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
        "QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s",
        "JTs","J9s","J8s","J7s","T9s","T8s","T7s",
        "98s","97s","87s","86s","76s","75s","65s","54s","43s",
        "AKo","AQo","AJo","ATo","A9o","A8o","A7o","A6o","A5o",
        "KQo","KJo","KTo","K9o","K8o","QJo","QTo","Q9o","JTo","J9o","T9o",
    },
}


# ---- vs RFI: 3bet (raise) and call ranges ----
# Keyed by (hero_position, villain_position) -> {"3bet": set, "call": set}
def _r(hands: str) -> set[str]:
    return set(hands.split())


VS_RFI: dict[tuple[str, str], dict[str, set[str]]] = {
    # BB vs BTN open
    ("BB", "BTN"): {
        "3bet": _r(
            "AA KK QQ JJ AKs AKo AQs A5s A4s KQs T9s 76s 65s 54s"
        ),
        "call": _r(
            "TT 99 88 77 66 55 44 33 22 AQo AJs ATs A9s A8s A7s A6s A3s A2s "
            "KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s "
            "QJs QTs Q9s Q8s Q7s Q6s Q5s Q4s "
            "JTs J9s J8s J7s J6s T8s T7s T6s 98s 97s 96s 87s 86s 85s 75s 74s 64s 53s 43s "
            "AJo ATo A9o KQo KJo KTo K9o QJo QTo Q9o JTo J9o T9o 98o"
        ),
    },
    ("BB", "CO"): {
        "3bet": _r("AA KK QQ JJ TT AKs AKo AQs AQo A5s A4s KQs"),
        "call": _r(
            "99 88 77 66 55 44 33 22 AJs ATs A9s A8s A7s A6s A3s A2s "
            "KJs KTs K9s K8s K7s QJs QTs Q9s Q8s JTs J9s J8s T9s T8s "
            "98s 87s 76s 65s 54s "
            "AJo ATo KQo KJo KTo QJo QTo JTo"
        ),
    },
    ("BB", "HJ"): {
        "3bet": _r("AA KK QQ JJ AKs AKo AQs AQo A5s KQs"),
        "call": _r(
            "TT 99 88 77 66 55 44 33 22 AJs ATs A9s A8s A4s A3s A2s "
            "KJs KTs K9s K8s QJs QTs Q9s JTs J9s T9s 98s 87s 76s 65s 54s "
            "AJo ATo KQo KJo QJo"
        ),
    },
    ("BB", "UTG"): {
        "3bet": _r("AA KK QQ JJ AKs AKo AQs A5s"),
        "call": _r(
            "TT 99 88 77 66 55 44 33 22 AQo AJs ATs A9s A8s A4s "
            "KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s "
            "AJo KQo"
        ),
    },
    ("BB", "SB"): {
        "3bet": _r(
            "AA KK QQ JJ TT 99 AKs AKo AQs AQo AJs AJo ATs KQs KQo "
            "A5s A4s A3s 76s 65s 54s 43s"
        ),
        "call": _r(
            "88 77 66 55 44 33 22 ATo A9s A8s A7s A6s A2s "
            "KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s "
            "QJs QTs Q9s Q8s Q7s Q6s "
            "JTs J9s J8s T9s T8s 98s 97s 87s 86s 75s 64s 53s "
            "KJo KTo QJo QTo JTo T9o"
        ),
    },
    # BTN vs CO open
    ("BTN", "CO"): {
        "3bet": _r("AA KK QQ JJ AKs AKo AQs AQo A5s A4s KQs"),
        "call": _r(
            "TT 99 88 77 66 55 44 AJs ATs A9s KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s "
            "AJo ATo KQo"
        ),
    },
    # CO vs UTG / HJ
    ("CO", "UTG"): {
        "3bet": _r("AA KK QQ AKs AKo A5s"),
        "call": _r(
            "JJ TT 99 88 77 AQs AQo AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s"
        ),
    },
    ("CO", "HJ"): {
        "3bet": _r("AA KK QQ JJ AKs AKo AQs A5s A4s"),
        "call": _r(
            "TT 99 88 77 66 AQo AJs ATs A9s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s"
        ),
    },
    # SB vs everyone (very tight 3bet, tight cold call)
    ("SB", "BTN"): {
        "3bet": _r(
            "AA KK QQ JJ TT AKs AKo AQs AQo AJs A5s A4s KQs"
        ),
        "call": _r(
            "99 88 77 66 55 ATs A9s KJs KTs QJs QTs JTs T9s 98s 87s 76s AJo KQo"
        ),
    },
    ("SB", "CO"): {
        "3bet": _r("AA KK QQ JJ AKs AKo AQs AQo A5s KQs"),
        "call": _r("TT 99 88 77 AJs ATs KJs QJs JTs T9s 98s 87s"),
    },
    ("SB", "HJ"): {
        "3bet": _r("AA KK QQ JJ AKs AKo AQs A5s"),
        "call": _r("TT 99 88 77 AQo AJs ATs KQs KJs QJs JTs T9s 98s 87s"),
    },
    ("SB", "UTG"): {
        "3bet": _r("AA KK QQ AKs AKo A5s"),
        "call": _r("JJ TT 99 88 77 AQs AQo AJs ATs KQs KJs QJs JTs T9s 98s"),
    },
    # BTN vs HJ / UTG
    ("BTN", "HJ"): {
        "3bet": _r("AA KK QQ JJ AKs AKo AQs A5s A4s"),
        "call": _r(
            "TT 99 88 77 66 55 AQo AJs ATs A9s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s "
            "AJo KQo"
        ),
    },
    ("BTN", "UTG"): {
        "3bet": _r("AA KK QQ AKs AKo A5s"),
        "call": _r(
            "JJ TT 99 88 77 66 AQs AQo AJs ATs A9s KQs KJs KTs QJs QTs JTs T9s 98s 87s"
        ),
    },
}


def get_rfi_chart(position: str) -> set[str]:
    return RFI_RANGES.get(position, set())


def get_vs_rfi_chart(hero_pos: str, villain_pos: str) -> dict[str, set[str]]:
    return VS_RFI.get((hero_pos, villain_pos), {"3bet": set(), "call": set()})
