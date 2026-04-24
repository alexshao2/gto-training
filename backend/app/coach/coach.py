"""Realtime GTO coach.

Given the current hand state and the user's chosen action, evaluates whether
the action deviates from the recommended GTO line. If so, returns a
structured `CoachFeedback` explaining what's wrong and why.

Logic by street:
  - PREFLOP: use pre-solved charts (RFI / vs RFI). 3bet/4bet pots covered.
  - POSTFLOP: heuristic based on
      * pot odds vs equity (for calls/folds)
      * SPR & hand strength (for bets/raises)
      * board texture (wet/dry, draw-heavy)
      * effective nuts/blockers
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..poker.cards import Card, hole_card_combo
from ..poker.equity import equity_vs_random
from ..poker.evaluator import (
    category_name,
    category_of,
    evaluate_best,
)
from ..poker.positions import position_label_6max
from ..poker.state import Action, HandState, Street
from .charts import get_rfi_chart, get_vs_rfi_chart


@dataclass
class CoachFeedback:
    is_mistake: bool
    severity: str  # "ok" | "minor" | "major" | "blunder"
    headline: str  # short summary, shown immediately
    detail: str  # longer explanation
    correct_action: str | None = None  # "fold"/"call"/"raise"/"check"/"bet"
    correct_size_bb: float | None = None
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "is_mistake": self.is_mistake,
            "severity": self.severity,
            "headline": self.headline,
            "detail": self.detail,
            "correct_action": self.correct_action,
            "correct_size_bb": self.correct_size_bb,
            "metrics": self.metrics,
        }


# ---------------- Preflop ----------------
def _preflop_situation(state: HandState, hero_seat: int) -> dict:
    """Classify preflop: open / facing-open / 3bet / etc."""
    hero_pos = position_label_6max(hero_seat, state.button_seat)
    actions_so_far = [h for h in state.history if h["street"] == "preflop"]
    raisers: list[int] = []
    for h in actions_so_far:
        if h["action"] and h["action"]["type"] in ("raise", "bet", "all_in"):
            raisers.append(h["seat"])
    n_raises = len(raisers)
    open_seat = raisers[0] if raisers else None
    open_pos = position_label_6max(open_seat, state.button_seat) if open_seat is not None else None
    return {
        "hero_pos": hero_pos,
        "n_raises": n_raises,
        "open_pos": open_pos,
        "open_seat": open_seat,
    }


def _preflop_coach(state: HandState, hero_seat: int, action: Action) -> CoachFeedback:
    p = state.players[hero_seat]
    combo = hole_card_combo(p.cards[0], p.cards[1])
    sit = _preflop_situation(state, hero_seat)
    hero_pos = sit["hero_pos"]
    n_raises = sit["n_raises"]
    open_pos = sit["open_pos"]

    chosen = action.type.value  # "fold" / "call" / "raise" / "check" / ...

    # --- RFI scenario (no prior raises, hero is not BB-with-just-blinds) ---
    if n_raises == 0:
        rfi = get_rfi_chart(hero_pos)
        should_raise = combo in rfi
        in_bb_walk = hero_pos == "BB"  # BB checks if folded around (only in SB raise scenario)
        if in_bb_walk and chosen == "check":
            return CoachFeedback(
                is_mistake=False,
                severity="ok",
                headline="Đúng — BB check khi không ai raise.",
                detail=f"{combo} ở BB, không có raise → check là free flop.",
            )
        if should_raise and chosen == "raise":
            return CoachFeedback(
                is_mistake=False,
                severity="ok",
                headline=f"GTO open: {combo} từ {hero_pos} là raise.",
                detail=f"{combo} nằm trong RFI range của {hero_pos}. Size chuẩn ~2.5bb (BTN/CO) hoặc 2.2bb (UTG/HJ).",
                correct_action="raise",
                correct_size_bb=2.5 if hero_pos in ("BTN", "CO", "SB") else 2.2,
            )
        if should_raise and chosen in ("fold", "call", "check"):
            return CoachFeedback(
                is_mistake=True,
                severity="major",
                headline=f"Sai — {combo} là open-raise ở {hero_pos}.",
                detail=(
                    f"Solver chart RFI cho {hero_pos} bao gồm {combo}. "
                    f"Hành động {chosen} làm mất EV: bạn từ bỏ initiative + fold equity, "
                    f"và cho phép villain phía sau open free."
                ),
                correct_action="raise",
                correct_size_bb=2.5 if hero_pos in ("BTN", "CO", "SB") else 2.2,
            )
        if not should_raise and chosen == "raise":
            return CoachFeedback(
                is_mistake=True,
                severity="major",
                headline=f"Sai — {combo} không phải open ở {hero_pos}.",
                detail=(
                    f"{combo} nằm ngoài solver RFI range của {hero_pos}. "
                    f"Open hand này -EV vì equity và playability không đủ; bạn sẽ "
                    f"OOP hoặc bị 3bet quá thường xuyên."
                ),
                correct_action="fold",
            )
        if not should_raise and chosen in ("fold", "check"):
            return CoachFeedback(
                is_mistake=False,
                severity="ok",
                headline=f"Đúng — fold {combo} ở {hero_pos}.",
                detail=f"{combo} ngoài RFI range của {hero_pos}, fold tiết kiệm chip.",
            )

    # --- Facing single open ---
    if n_raises == 1 and open_pos and open_pos != hero_pos:
        chart = get_vs_rfi_chart(hero_pos, open_pos)
        in_3bet = combo in chart["3bet"]
        in_call = combo in chart["call"]

        if in_3bet and chosen == "raise":
            return CoachFeedback(
                is_mistake=False,
                severity="ok",
                headline=f"GTO 3bet {combo} từ {hero_pos} vs {open_pos} open.",
                detail="Hand này có equity + blocker mạnh và nằm trong polarized 3bet range.",
                correct_action="raise",
                correct_size_bb=11.0 if hero_pos in ("SB", "BB") else 9.0,
            )
        if in_3bet and chosen == "call":
            return CoachFeedback(
                is_mistake=True,
                severity="minor",
                headline=f"Suboptimal — {combo} là 3bet thay vì call.",
                detail=(
                    f"{hero_pos} vs {open_pos}: {combo} trong 3bet range. Call sẽ thiếu fold equity, "
                    f"cho nhiều người tham gia, và hand bị over-realize equity giảm."
                ),
                correct_action="raise",
                correct_size_bb=11.0 if hero_pos in ("SB", "BB") else 9.0,
            )
        if in_3bet and chosen == "fold":
            return CoachFeedback(
                is_mistake=True,
                severity="blunder",
                headline=f"BLUNDER — fold {combo} là quá tight.",
                detail=(
                    f"Solver xếp {combo} vào 3bet range vs {open_pos}. Fold ở đây bỏ qua "
                    f"hand có equity tốt + blocker, là 1 trong những leak lớn nhất ở mid-stakes."
                ),
                correct_action="raise",
                correct_size_bb=11.0 if hero_pos in ("SB", "BB") else 9.0,
            )
        if in_call and chosen == "call":
            return CoachFeedback(
                is_mistake=False,
                severity="ok",
                headline=f"GTO call {combo} vs {open_pos} open.",
                detail="Hand có playability postflop, equity đủ cho pot odds.",
                correct_action="call",
            )
        if in_call and chosen == "raise":
            return CoachFeedback(
                is_mistake=True,
                severity="minor",
                headline=f"Over-bluff — {combo} là call, không phải 3bet.",
                detail=(
                    f"{combo} thuộc flat range. 3bet với hand này tạo polarized leak: "
                    f"villain 4bet bạn buộc phải fold equity tốt."
                ),
                correct_action="call",
            )
        if in_call and chosen == "fold":
            return CoachFeedback(
                is_mistake=True,
                severity="major",
                headline=f"Quá tight — {combo} có pot odds + equity để call.",
                detail=f"Solver call {combo} vs {open_pos} open. Fold = passing on +EV spot.",
                correct_action="call",
            )
        # Hand outside both ranges
        if not in_3bet and not in_call:
            if chosen == "fold":
                return CoachFeedback(
                    is_mistake=False,
                    severity="ok",
                    headline=f"Đúng — fold {combo} vs {open_pos} open.",
                    detail=f"{combo} ngoài cả 3bet và call range của {hero_pos} vs {open_pos}.",
                    correct_action="fold",
                )
            return CoachFeedback(
                is_mistake=True,
                severity="major",
                headline=f"Sai — {combo} nên fold vs {open_pos} open.",
                detail=(
                    f"Hand này ngoài cả 3bet và call range. {chosen.capitalize()} sẽ -EV: "
                    f"equity quá thấp, dominated rất thường xuyên."
                ),
                correct_action="fold",
            )

    # Fallback (3bet pots, multiway, etc.)
    return CoachFeedback(
        is_mistake=False,
        severity="ok",
        headline="Spot phức tạp — coach đang dùng heuristic.",
        detail=(
            "Đây là 3bet/4bet pot hoặc multiway. Pre-solved charts hiện chỉ phủ "
            "RFI và vs-RFI. Tham khảo rule-of-thumb: 4bet với QQ+/AKs+/AKo, "
            "fold mọi thứ khác trừ khi có lý do exploit."
        ),
    )


# ---------------- Postflop ----------------
def _board_texture(board: list[Card]) -> dict:
    """Quick wet/dry classifier."""
    suits = [c.suit for c in board]
    ranks = sorted([c.rank.value for c in board], reverse=True)
    flush_count = max(suits.count(s) for s in set(suits)) if suits else 0
    paired = len(set(ranks)) < len(ranks)
    connected = False
    if len(ranks) >= 2:
        gaps = [ranks[i] - ranks[i + 1] for i in range(len(ranks) - 1)]
        connected = max(gaps) <= 2 and min(ranks) >= 4
    high_card = max(ranks) if ranks else 0
    wet_score = (flush_count - 1) * 2 + (2 if connected else 0) + (1 if paired else 0)
    return {
        "flush_draw_present": flush_count >= 2,
        "monotone": flush_count >= 3,
        "paired": paired,
        "connected": connected,
        "high_card": high_card,
        "wet_score": wet_score,
        "is_wet": wet_score >= 3,
    }


def _hand_strength_label(score: int, board_len: int) -> str:
    cat = category_of(score)
    names = {0: "high card", 1: "one pair", 2: "two pair", 3: "trips/set",
             4: "straight", 5: "flush", 6: "full house", 7: "quads", 8: "straight flush"}
    return names.get(cat, "unknown")


def _postflop_coach(state: HandState, hero_seat: int, action: Action) -> CoachFeedback:
    p = state.players[hero_seat]
    legal = state.legal_actions(hero_seat)
    chosen = action.type.value
    pot = state.pot
    to_call = legal["to_call"]
    pot_after_call = pot + to_call
    pot_odds = to_call / pot_after_call if pot_after_call > 0 else 0.0
    rng = random.Random(hash((tuple(p.cards or []), tuple(state.board))) & 0xFFFFFFFF)
    eq = equity_vs_random(p.cards, state.board, iters=300, rng=rng)
    score = evaluate_best([*p.cards, *state.board])
    strength = _hand_strength_label(score, len(state.board))
    texture = _board_texture(state.board)
    spr = (p.stack / max(pot, 1)) if pot > 0 else float("inf")

    metrics = {
        "equity_vs_random": round(eq, 3),
        "pot_odds": round(pot_odds, 3),
        "spr": round(spr, 2) if spr != float("inf") else None,
        "hand_strength": strength,
        "category": category_name(score),
        "board_texture": {
            "is_wet": texture["is_wet"],
            "monotone": texture["monotone"],
            "paired": texture["paired"],
            "connected": texture["connected"],
        },
    }

    # --- Facing a bet: fold vs call vs raise ---
    if to_call > 0:
        if chosen == "fold":
            if eq >= pot_odds + 0.10 and category_of(score) >= 1:
                return CoachFeedback(
                    is_mistake=True,
                    severity="major",
                    headline=f"Fold quá nhanh — equity {eq:.0%} > pot odds {pot_odds:.0%}.",
                    detail=(
                        f"Bạn cầm {category_name(score)} với equity ~{eq:.0%}, pot odds chỉ "
                        f"yêu cầu {pot_odds:.0%}. Đây là +EV call, board texture "
                        f"{'wet' if texture['is_wet'] else 'dry'}."
                    ),
                    correct_action="call",
                    metrics=metrics,
                )
            return CoachFeedback(
                is_mistake=False,
                severity="ok",
                headline=f"Fold OK — equity {eq:.0%} dưới pot odds {pot_odds:.0%}.",
                detail=f"Hand strength: {category_name(score)}. Không có giá để call.",
                correct_action="fold",
                metrics=metrics,
            )
        if chosen == "call":
            if eq < pot_odds - 0.05 and category_of(score) <= 1:
                return CoachFeedback(
                    is_mistake=True,
                    severity="major",
                    headline=f"Call -EV — equity {eq:.0%} < pot odds {pot_odds:.0%}.",
                    detail=(
                        f"{category_name(score)} không đủ equity để call. Bạn đang đốt chip."
                    ),
                    correct_action="fold",
                    metrics=metrics,
                )
            if category_of(score) >= 6 and texture["is_wet"]:
                return CoachFeedback(
                    is_mistake=True,
                    severity="minor",
                    headline=f"Slowplay nguy hiểm — {category_name(score)} trên board ướt.",
                    detail=(
                        "Board nhiều draw (flush/straight). Slowplay khiến bạn không "
                        "build pot và cho free card. Nên raise để protect và value-thin."
                    ),
                    correct_action="raise",
                    metrics=metrics,
                )
            return CoachFeedback(
                is_mistake=False,
                severity="ok",
                headline=f"Call OK ({category_name(score)}, eq {eq:.0%}).",
                detail=f"Pot odds {pot_odds:.0%}, equity {eq:.0%} → +EV call.",
                correct_action="call",
                metrics=metrics,
            )
        if chosen in ("raise", "all_in"):
            if category_of(score) <= 0 and eq < 0.40:
                return CoachFeedback(
                    is_mistake=True,
                    severity="major",
                    headline="Bluff-raise mỏng — hand quá yếu, không có blocker.",
                    detail=(
                        f"Equity {eq:.0%}, hand chỉ là {category_name(score)}. "
                        f"Raise/jam ở đây là spew chip; villain không fold đủ "
                        f"và bạn không có equity backup."
                    ),
                    correct_action="fold",
                    metrics=metrics,
                )
            return CoachFeedback(
                is_mistake=False,
                severity="ok",
                headline=f"Raise OK — {category_name(score)}, eq {eq:.0%}.",
                detail="Value raise build pot và denial equity của draw.",
                correct_action="raise",
                metrics=metrics,
            )

    # --- No bet to face: check vs bet ---
    if chosen == "check":
        if category_of(score) >= 3 and texture["is_wet"]:
            return CoachFeedback(
                is_mistake=True,
                severity="minor",
                headline=f"Check sai — {category_name(score)} trên board ướt cần bet.",
                detail=(
                    "Board có draw (flush/straight). Check cho free card và mất value. "
                    "Bet 50-75% pot để protect + value."
                ),
                correct_action="bet",
                metrics=metrics,
            )
        return CoachFeedback(
            is_mistake=False,
            severity="ok",
            headline="Check OK trên spot này.",
            detail=f"{category_name(score)}, eq {eq:.0%}. Pot control hợp lý.",
            correct_action="check",
            metrics=metrics,
        )
    if chosen == "bet":
        if category_of(score) == 0 and eq < 0.35:
            return CoachFeedback(
                is_mistake=True,
                severity="major",
                headline="Bluff không có equity — không nên fire.",
                detail=(
                    f"High card với eq {eq:.0%}. Không có draw backup, không có blocker mạnh. "
                    f"Check & give up."
                ),
                correct_action="check",
                metrics=metrics,
            )
        return CoachFeedback(
            is_mistake=False,
            severity="ok",
            headline=f"Bet OK ({category_name(score)}, eq {eq:.0%}).",
            detail="Build pot for value / deny equity.",
            correct_action="bet",
            metrics=metrics,
        )
    return CoachFeedback(
        is_mistake=False,
        severity="ok",
        headline="Action acceptable.",
        detail=f"Equity {eq:.0%}, hand {category_name(score)}.",
        metrics=metrics,
    )


def evaluate_action(state: HandState, hero_seat: int, action: Action) -> CoachFeedback:
    """Top-level entry: route to preflop or postflop coach."""
    if state.street == Street.PREFLOP:
        return _preflop_coach(state, hero_seat, action)
    return _postflop_coach(state, hero_seat, action)
