import { create } from "zustand";
import {
  createSession,
  fetchProfiles,
  nextHand,
  submitAction,
} from "../api/client";
import type { Action, CreateSessionRequest, SessionSnapshot } from "../types/api";

interface SessionStore {
  snapshot: SessionSnapshot | null;
  loading: boolean;
  error: string | null;
  profiles: Record<string, string>;
  loadProfiles: () => Promise<void>;
  startSession: (req: CreateSessionRequest) => Promise<void>;
  act: (action: Action, amount?: number) => Promise<void>;
  newHand: () => Promise<void>;
  setSnapshot: (s: SessionSnapshot) => void;
  reset: () => void;
}

export const useSession = create<SessionStore>((set, get) => ({
  snapshot: null,
  loading: false,
  error: null,
  profiles: {},

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
      set({ snapshot: snap, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  async act(action, amount = 0) {
    const { snapshot } = get();
    if (!snapshot) return;
    set({ loading: true });
    try {
      const snap = await submitAction(snapshot.session_id, action, amount);
      set({ snapshot: snap, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  async newHand() {
    const { snapshot } = get();
    if (!snapshot) return;
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
    set({ snapshot: null, error: null });
  },
}));
