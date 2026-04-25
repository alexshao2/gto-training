"""Tests for the TTS proxy and audio store."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.session import _short_speech_text
from app.coach import tts as tts_mod
from app.coach.coach import CoachFeedback
from app.main import create_app


@pytest.fixture(autouse=True)
def _reset_store():
    tts_mod.AUDIO_STORE.clear()
    tts_mod._TEXT_INDEX.clear()
    yield
    tts_mod.AUDIO_STORE.clear()
    tts_mod._TEXT_INDEX.clear()


def test_short_speech_text_with_correct_action() -> None:
    fb = CoachFeedback(
        is_mistake=True,
        severity="major",
        headline="Bạn fold quá lỏng",
        detail="AKs trên CO vs UTG raise là 3bet hoặc call. Equity 42% đủ để chơi tiếp.",
        correct_action="3bet",
        correct_size_bb=9,
    )
    spoken = _short_speech_text(fb)
    assert "Bạn fold quá lỏng." in spoken
    assert "AKs trên CO vs UTG" in spoken
    assert "GTO line là 3bet" in spoken
    assert "9bb" in spoken
    assert len(spoken) <= 600


def test_short_speech_text_handles_empty_detail() -> None:
    fb = CoachFeedback(
        is_mistake=False,
        severity="ok",
        headline="Hành động đúng",
        detail="",
    )
    assert _short_speech_text(fb) == "Hành động đúng."


@pytest.mark.asyncio
async def test_kick_off_synthesis_returns_none_without_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = await tts_mod.kick_off_synthesis("xin chào")
    assert out is None


@pytest.mark.asyncio
async def test_kick_off_and_get_audio_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def fake_synth(text: str, *, model: str = "google-tts/vi") -> bytes:
        return b"FAKE_MP3_BYTES_" + text.encode()

    with patch.object(tts_mod, "synthesize", side_effect=fake_synth):
        audio_id = await tts_mod.kick_off_synthesis("xin chào")
        assert audio_id is not None
        data = await tts_mod.get_audio(audio_id, timeout=2.0)
        assert data is not None
        assert b"FAKE_MP3_BYTES_xin ch" in data

        # Same text should hit the content cache and reuse the audio_id.
        again = await tts_mod.kick_off_synthesis("xin chào")
        assert again == audio_id


@pytest.mark.asyncio
async def test_get_audio_returns_none_for_unknown_id() -> None:
    out = await tts_mod.get_audio("does-not-exist", timeout=0.1)
    assert out is None


def test_tts_get_endpoint_serves_mp3(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def fake_synth(text: str, *, model: str = "google-tts/vi") -> bytes:
        return b"ID3FAKE" + text.encode()

    with patch.object(tts_mod, "synthesize", side_effect=fake_synth):
        audio_id = asyncio.run(tts_mod.kick_off_synthesis("hello world"))
        assert audio_id

        client = TestClient(create_app())
        r = client.get(f"/api/tts/{audio_id}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/mpeg"
        assert r.content.startswith(b"ID3FAKE")


def test_tts_get_endpoint_404_for_unknown() -> None:
    client = TestClient(create_app())
    r = client.get("/api/tts/nope")
    assert r.status_code == 404
