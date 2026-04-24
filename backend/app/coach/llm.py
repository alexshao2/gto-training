"""Optional LLM layer that turns CoachFeedback metrics into rich, in-context
explanations (Vietnamese). Falls back to the rule-based detail string if no
API key is present.
"""
from __future__ import annotations

import json
import os

import httpx

from .coach import CoachFeedback

SYSTEM_PROMPT = (
    "Bạn là HLV poker GTO chuyên nghiệp, dạy MTT và cash 6-max. "
    "Trả lời ngắn gọn (3-5 câu), bằng tiếng Việt, nói đúng vào điểm "
    "mà học viên sai và TẠI SAO sai theo logic GTO (range, equity, EV, "
    "blockers, board texture, ICM khi liên quan). Tránh sáo rỗng. "
    "Nếu hành động đúng, xác nhận ngắn và nêu lý do solver chọn line đó."
)


async def enrich_feedback(
    feedback: CoachFeedback,
    *,
    state_summary: dict,
    hero_combo: str,
) -> CoachFeedback:
    """Optionally enrich the `detail` field via an LLM call."""
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return feedback
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            text = await _ask_anthropic(feedback, state_summary, hero_combo)
        else:
            text = await _ask_openai(feedback, state_summary, hero_combo)
        if text:
            feedback.detail = text
    except Exception as e:  # noqa: BLE001 - best-effort enrichment
        feedback.detail += f"\n\n(LLM enrichment failed: {type(e).__name__})"
    return feedback


def _user_prompt(feedback: CoachFeedback, state_summary: dict, combo: str) -> str:
    payload = {
        "user_combo": combo,
        "feedback_headline": feedback.headline,
        "feedback_default_detail": feedback.detail,
        "is_mistake": feedback.is_mistake,
        "severity": feedback.severity,
        "metrics": feedback.metrics,
        "state": state_summary,
    }
    return (
        "Phân tích tình huống poker dưới đây và viết feedback realtime cho "
        "học viên. Tham chiếu metrics nếu có. Dữ liệu (JSON):\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


async def _ask_anthropic(
    feedback: CoachFeedback, state_summary: dict, combo: str
) -> str | None:
    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 400,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": _user_prompt(feedback, state_summary, combo)}
                ],
            },
        )
        r.raise_for_status()
        data = r.json()
        return data["content"][0]["text"].strip() if data.get("content") else None


async def _ask_openai(
    feedback: CoachFeedback, state_summary: dict, combo: str
) -> str | None:
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _user_prompt(feedback, state_summary, combo)},
                ],
                "temperature": 0.4,
                "max_tokens": 400,
            },
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip() if data.get("choices") else None
