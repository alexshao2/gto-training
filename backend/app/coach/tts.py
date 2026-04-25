"""Text-to-speech proxy for the coach.

Calls the user's OpenAI-compatible LLM proxy at `${OPENAI_BASE_URL}/audio/speech`
to synthesize Vietnamese speech. The bytes are stored in an in-memory LRU so
the frontend can stream them via `GET /api/tts/{audio_id}`.

Design notes:
- We pre-generate audio asynchronously, in parallel with LLM enrichment, so the
  TTS call adds zero latency to the action response (LLM call is the long pole).
- The audio_id (uuid) is returned synchronously inside the snapshot. The MP3
  bytes land in `AUDIO_STORE` shortly after. The serving endpoint long-polls on
  an asyncio.Event so the frontend can request the audio immediately and get a
  smooth streaming experience.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from collections import OrderedDict

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TTS_MODEL = "google-tts/vi"
MAX_TEXT_LEN = 600  # Cap input to avoid huge synthesis cost.
MAX_STORE_ENTRIES = 256
WAIT_TIMEOUT_SECONDS = 12.0


class _AudioEntry:
    __slots__ = ("event", "data", "error")

    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.data: bytes | None = None
        self.error: str | None = None


# Maps audio_id -> _AudioEntry. OrderedDict for LRU eviction.
AUDIO_STORE: OrderedDict[str, _AudioEntry] = OrderedDict()
# Maps text-hash -> audio_id for content-level cache (skip TTS on identical text).
_TEXT_INDEX: dict[str, str] = {}
_LOCK = asyncio.Lock()


def _hash_text(text: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\0")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _evict_if_needed() -> None:
    while len(AUDIO_STORE) > MAX_STORE_ENTRIES:
        old_id, _ = AUDIO_STORE.popitem(last=False)
        # Also drop text index entries pointing at the evicted id.
        for k, v in list(_TEXT_INDEX.items()):
            if v == old_id:
                _TEXT_INDEX.pop(k, None)


async def kick_off_synthesis(text: str, *, model: str | None = None) -> str | None:
    """Schedule a TTS synthesis and return an audio_id immediately.

    Returns None when no API key is configured, signaling the frontend to skip
    audio rendering. The returned id can be used in `GET /api/tts/{id}`.
    """
    text = (text or "").strip()
    if not text:
        return None
    if len(text) > MAX_TEXT_LEN:
        text = text[:MAX_TEXT_LEN]
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        return None
    actual_model = model or os.environ.get("TTS_MODEL", DEFAULT_TTS_MODEL)
    key = _hash_text(text, actual_model)
    async with _LOCK:
        cached = _TEXT_INDEX.get(key)
        if cached and cached in AUDIO_STORE:
            # Refresh LRU position.
            AUDIO_STORE.move_to_end(cached)
            return cached
        audio_id = str(uuid.uuid4())
        entry = _AudioEntry()
        AUDIO_STORE[audio_id] = entry
        _TEXT_INDEX[key] = audio_id
        _evict_if_needed()
    asyncio.create_task(_synthesize_into(audio_id, text, actual_model))
    return audio_id


async def _synthesize_into(audio_id: str, text: str, model: str) -> None:
    entry = AUDIO_STORE.get(audio_id)
    if entry is None:
        return
    try:
        entry.data = await synthesize(text, model=model)
    except Exception as e:  # noqa: BLE001 - best-effort; surface as event signal
        logger.warning("TTS synth failed: %s", e)
        entry.error = f"{type(e).__name__}: {e}"
    finally:
        entry.event.set()


async def synthesize(text: str, *, model: str = DEFAULT_TTS_MODEL) -> bytes:
    """Call the OpenAI-compatible /audio/speech endpoint and return MP3 bytes."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/audio/speech"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "input": text},
        )
        r.raise_for_status()
        return r.content


async def get_audio(audio_id: str, *, timeout: float = WAIT_TIMEOUT_SECONDS) -> bytes | None:
    """Return MP3 bytes for an audio_id, waiting up to `timeout` for synthesis.

    Returns None if id unknown or synthesis errored.
    """
    entry = AUDIO_STORE.get(audio_id)
    if entry is None:
        return None
    if not entry.event.is_set():
        try:
            await asyncio.wait_for(entry.event.wait(), timeout=timeout)
        except TimeoutError:
            return None
    if entry.error:
        return None
    AUDIO_STORE.move_to_end(audio_id)
    return entry.data
