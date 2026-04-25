// Lightweight Web Audio synth for poker UI sounds. No assets needed.
// Each sound is a short envelope-shaped oscillator burst.

let ctx: AudioContext | null = null;
let muted = false;

const STORAGE_KEY = "poker_gto_sound_muted";

try {
  muted = localStorage.getItem(STORAGE_KEY) === "1";
} catch {
  // ignore (private mode etc.)
}

function getCtx(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!ctx) {
    const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    try {
      ctx = new Ctor();
    } catch {
      return null;
    }
  }
  // resume on first interaction
  if (ctx.state === "suspended") {
    void ctx.resume();
  }
  return ctx;
}

interface ToneOpts {
  freq: number;
  type?: OscillatorType;
  duration?: number;
  attack?: number;
  release?: number;
  gain?: number;
  pitchEnd?: number;
}

function tone({
  freq,
  type = "sine",
  duration = 0.08,
  attack = 0.005,
  release = 0.06,
  gain = 0.18,
  pitchEnd,
}: ToneOpts) {
  const c = getCtx();
  if (!c || muted) return;
  const t = c.currentTime;
  const osc = c.createOscillator();
  const g = c.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  if (pitchEnd != null) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(20, pitchEnd), t + duration);
  }
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(gain, t + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t + duration + release);
  osc.connect(g).connect(c.destination);
  osc.start(t);
  osc.stop(t + duration + release + 0.05);
}

function noiseBurst(duration: number, gain: number, filterFreq: number) {
  const c = getCtx();
  if (!c || muted) return;
  const t = c.currentTime;
  const buffer = c.createBuffer(1, Math.floor(c.sampleRate * duration), c.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i++) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
  }
  const src = c.createBufferSource();
  src.buffer = buffer;
  const filter = c.createBiquadFilter();
  filter.type = "highpass";
  filter.frequency.setValueAtTime(filterFreq, t);
  const g = c.createGain();
  g.gain.setValueAtTime(gain, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + duration);
  src.connect(filter).connect(g).connect(c.destination);
  src.start(t);
}

export const sfx = {
  cardDeal: () => noiseBurst(0.08, 0.15, 1500),
  cardFlip: () => {
    tone({ freq: 600, type: "triangle", duration: 0.05, gain: 0.12 });
    setTimeout(() => tone({ freq: 800, type: "triangle", duration: 0.05, gain: 0.1 }), 30);
  },
  chipClink: () => {
    tone({ freq: 1800, type: "square", duration: 0.04, gain: 0.08, pitchEnd: 1200 });
    setTimeout(
      () => tone({ freq: 2200, type: "square", duration: 0.03, gain: 0.06, pitchEnd: 1500 }),
      40
    );
  },
  chipSlide: () => {
    noiseBurst(0.18, 0.08, 800);
    setTimeout(() => tone({ freq: 1600, type: "square", duration: 0.04, gain: 0.07 }), 80);
  },
  buttonClick: () => tone({ freq: 600, type: "triangle", duration: 0.04, gain: 0.1, pitchEnd: 480 }),
  check: () => tone({ freq: 520, type: "sine", duration: 0.08, gain: 0.12 }),
  fold: () => noiseBurst(0.12, 0.1, 600),
  raise: () => {
    tone({ freq: 440, type: "triangle", duration: 0.06, gain: 0.13 });
    setTimeout(() => tone({ freq: 660, type: "triangle", duration: 0.08, gain: 0.13 }), 60);
  },
  allIn: () => {
    tone({ freq: 330, type: "sawtooth", duration: 0.08, gain: 0.13 });
    setTimeout(() => tone({ freq: 660, type: "sawtooth", duration: 0.1, gain: 0.13 }), 70);
    setTimeout(() => tone({ freq: 990, type: "sawtooth", duration: 0.12, gain: 0.13 }), 140);
  },
  win: () => {
    tone({ freq: 523, type: "triangle", duration: 0.12, gain: 0.16 });
    setTimeout(() => tone({ freq: 659, type: "triangle", duration: 0.12, gain: 0.16 }), 110);
    setTimeout(() => tone({ freq: 784, type: "triangle", duration: 0.18, gain: 0.18 }), 220);
    setTimeout(() => tone({ freq: 1046, type: "triangle", duration: 0.28, gain: 0.18 }), 380);
  },
  lose: () => {
    tone({ freq: 380, type: "sawtooth", duration: 0.18, gain: 0.13, pitchEnd: 200 });
  },
  warn: () => {
    tone({ freq: 880, type: "square", duration: 0.05, gain: 0.1 });
    setTimeout(() => tone({ freq: 880, type: "square", duration: 0.05, gain: 0.1 }), 110);
  },
  tick: () => tone({ freq: 1100, type: "square", duration: 0.02, gain: 0.05 }),
};

export function isMuted(): boolean {
  return muted;
}

export function setMuted(m: boolean) {
  muted = m;
  try {
    localStorage.setItem(STORAGE_KEY, m ? "1" : "0");
  } catch {
    // ignore
  }
}

export function toggleMuted(): boolean {
  setMuted(!muted);
  return muted;
}
