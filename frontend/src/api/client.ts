import type {
  Action,
  CreateSessionRequest,
  SessionSnapshot,
} from "../types/api";

const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8080";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!r.ok) {
    let detail = "";
    try {
      const j = await r.json();
      detail = j.detail ?? JSON.stringify(j);
    } catch {
      detail = await r.text();
    }
    throw new Error(`API ${r.status}: ${detail}`);
  }
  return (await r.json()) as T;
}

export async function fetchProfiles(): Promise<Record<string, string>> {
  return http<Record<string, string>>("/api/profiles");
}

export async function createSession(
  req: CreateSessionRequest
): Promise<SessionSnapshot> {
  return http<SessionSnapshot>("/api/sessions", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getSession(id: string): Promise<SessionSnapshot> {
  return http<SessionSnapshot>(`/api/sessions/${id}`);
}

export async function submitAction(
  id: string,
  action: Action,
  amount = 0
): Promise<SessionSnapshot> {
  return http<SessionSnapshot>(`/api/sessions/${id}/action`, {
    method: "POST",
    body: JSON.stringify({ action, amount }),
  });
}

export async function nextHand(id: string): Promise<SessionSnapshot> {
  return http<SessionSnapshot>(`/api/sessions/${id}/next_hand`, {
    method: "POST",
  });
}

export function wsUrl(sessionId: string): string {
  const httpBase = API_BASE;
  const wsBase = httpBase.replace(/^http/, "ws");
  return `${wsBase}/api/ws/${sessionId}`;
}

export { API_BASE };
