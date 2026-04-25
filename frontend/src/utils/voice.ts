/**
 * Voice (TTS) playback singleton.
 *
 * The backend pre-generates an MP3 for each coach feedback and exposes it at
 * `audio_url` (e.g. `/api/tts/<id>`). This module owns a single global
 * `HTMLAudioElement` so each new feedback cleanly cancels the previous audio.
 *
 * The audio_url returns a long-poll: the server waits up to ~10s for the TTS
 * synthesis task to finish and then streams MP3 bytes. We pair that with an
 * `<audio>` element which buffers progressively, so the user hears speech
 * within ~1-2s of the snapshot landing.
 */
import { API_BASE } from "../api/client";

const VOICE_KEY = "voice_enabled";

let audioEl: HTMLAudioElement | null = null;
let lastUrl: string | null = null;
const listeners = new Set<(playing: boolean) => void>();

function ensureAudio(): HTMLAudioElement {
  if (!audioEl) {
    audioEl = new Audio();
    audioEl.preload = "auto";
    audioEl.addEventListener("playing", () => emit(true));
    audioEl.addEventListener("pause", () => emit(false));
    audioEl.addEventListener("ended", () => emit(false));
    audioEl.addEventListener("error", () => emit(false));
  }
  return audioEl;
}

function emit(playing: boolean): void {
  for (const fn of listeners) fn(playing);
}

export function isVoiceEnabled(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(VOICE_KEY) !== "false";
}

export function setVoiceEnabled(v: boolean): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(VOICE_KEY, v ? "true" : "false");
  if (!v) stop();
}

export function onPlayingChange(fn: (playing: boolean) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function resolveSrc(audioUrl: string): string {
  if (audioUrl.startsWith("http://") || audioUrl.startsWith("https://")) {
    return audioUrl;
  }
  return `${API_BASE}${audioUrl}`;
}

/**
 * Play the audio referenced by `audioUrl`. Stops any previous audio first.
 * Safe no-op when voice is disabled. Errors are swallowed so a TTS failure
 * never breaks the UI.
 */
export async function playFromUrl(audioUrl: string | null | undefined): Promise<void> {
  if (!audioUrl) return;
  if (!isVoiceEnabled()) return;
  const src = resolveSrc(audioUrl);
  if (lastUrl === src && audioEl && !audioEl.paused) return; // already playing
  const el = ensureAudio();
  try {
    el.pause();
  } catch {
    /* ignore */
  }
  el.src = src;
  lastUrl = src;
  try {
    await el.play();
  } catch {
    // Autoplay blocked or network failure — silent fail; user can hit replay.
    emit(false);
  }
}

/**
 * Synthesize arbitrary text on demand (e.g. user expanded "đọc chi tiết") and
 * play it. Uses POST /api/tts which returns the MP3 directly.
 */
export async function speakText(text: string): Promise<void> {
  if (!isVoiceEnabled()) return;
  if (!text.trim()) return;
  try {
    const r = await fetch(`${API_BASE}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!r.ok) return;
    const blob = await r.blob();
    const objUrl = URL.createObjectURL(blob);
    const el = ensureAudio();
    try {
      el.pause();
    } catch {
      /* ignore */
    }
    if (lastUrl && lastUrl.startsWith("blob:")) {
      try {
        URL.revokeObjectURL(lastUrl);
      } catch {
        /* ignore */
      }
    }
    el.src = objUrl;
    lastUrl = objUrl;
    await el.play();
  } catch {
    emit(false);
  }
}

export function stop(): void {
  if (!audioEl) return;
  try {
    audioEl.pause();
    audioEl.currentTime = 0;
  } catch {
    /* ignore */
  }
  emit(false);
}

export function isPlaying(): boolean {
  return !!audioEl && !audioEl.paused && !audioEl.ended;
}
