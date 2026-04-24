import { create } from "zustand";
import {
  createSession,
  fetchProfiles,
  nextHand,
  submitAction,
  wsUrl,
} from "../api/client";
import type { Action, CreateSessionRequest, SessionSnapshot } from "../types/api";

interface SessionStore {
  snapshot: SessionSnapshot | null;
  loading: boolean;
  error: string | null;
  profiles: Record<string, string>;
  ws: WebSocket | null;
  loadProfiles: () => Promise<void>;
  startSession: (req: CreateSessionRequest) => Promise<void>;
  act: (action: Action, amount?: number) => Promise<void>;
  newHand: () => Promise<void>;
  setSnapshot: (s: SessionSnapshot) => void;
  reset: () => void;
}

function connectWs(sessionId: string, onSnap: (s: SessionSnapshot) => void): WebSocket {
  const ws = new WebSocket(wsUrl(sessionId));
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "snapshot" && msg.data) {
        onSnap(msg.data as SessionSnapshot);
      }
    } catch {
      // ignore parse errors
    }
  };
  return ws;
}

export const useSession = create<SessionStore>((set, get) => ({
  snapshot: null,
  loading: false,
  error: null,
  profiles: {},
  ws: null,

  async loadProfiles() {
    try {
      const p = await fetchProfiles();
      set({ profiles: p });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  async startSession(req) {
    set({ loading: true, error: null });
    try {
      const snap = await createSession(req);
      const onSnap = (s: SessionSnapshot) => set({ snapshot: s });
      const ws = connectWs(snap.session_id, onSnap);
      set({ snapshot: snap, loading: false, ws });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  async act(action, amount = 0) {
    const { snapshot, ws } = get();
    if (!snapshot) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "action", action, amount }));
      return;
    }
    set({ loading: true });
    try {
      const snap = await submitAction(snapshot.session_id, action, amount);
      set({ snapshot: snap, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  async newHand() {
    const { snapshot, ws } = get();
    if (!snapshot) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "next_hand" }));
      return;
    }
    set({ loading: true });
    try {
      const snap = await nextHand(snapshot.session_id);
      set({ snapshot: snap, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  setSnapshot(s) {
    set({ snapshot: s });
  },

  reset() {
    const { ws } = get();
    if (ws) {
      try {
        ws.close();
      } catch {
        // ignore
      }
    }
    set({ snapshot: null, error: null, ws: null });
  },
}));
