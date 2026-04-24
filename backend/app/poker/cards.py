"""Card, deck, and rank/suit primitives for No-Limit Hold'em."""
from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3

    @property
    def char(self) -> str:
        return "cdhs"[self.value]


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def char(self) -> str:
        return "23456789TJQKA"[self.value - 2]


@dataclass(frozen=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.char}{self.suit.char}"

    @classmethod
    def from_str(cls, s: str) -> Card:
        if len(s) != 2:
            raise ValueError(f"Invalid card string: {s!r}")
        rank_char, suit_char = s[0].upper(), s[1].lower()
        rank = Rank("23456789TJQKA".index(rank_char) + 2)
        suit = Suit("cdhs".index(suit_char))
        return cls(rank, suit)

    @property
    def code(self) -> int:
        """4 * rank_idx + suit, useful for fast indexing (0..51)."""
        return (self.rank.value - 2) * 4 + self.suit.value


def all_cards() -> list[Card]:
    return [Card(Rank(r), Suit(s)) for r in range(2, 15) for s in range(4)]


class Deck:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._cards: list[Card] = all_cards()
        self._rng.shuffle(self._cards)

    def deal(self, n: int) -> list[Card]:
        if n > len(self._cards):
            raise ValueError("Not enough cards in deck")
        out, self._cards = self._cards[:n], self._cards[n:]
        return out

    def remove(self, cards: Iterable[Card]) -> None:
        s = set(cards)
        self._cards = [c for c in self._cards if c not in s]

    def __len__(self) -> int:
        return len(self._cards)


def hand_to_str(cards: Iterable[Card]) -> str:
    return " ".join(str(c) for c in cards)


def parse_hand(s: str) -> list[Card]:
    return [Card.from_str(tok) for tok in s.replace(",", " ").split()]


def hole_card_combo(c1: Card, c2: Card) -> str:
    """Return canonical preflop combo notation: 'AKs', 'AKo', '99', etc."""
    a, b = (c1, c2) if c1.rank >= c2.rank else (c2, c1)
    if a.rank == b.rank:
        return f"{a.rank.char}{b.rank.char}"
    suited = "s" if a.suit == b.suit else "o"
    return f"{a.rank.char}{b.rank.char}{suited}"
