export type Action =
  | "fold"
  | "check"
  | "call"
  | "bet"
  | "raise"
  | "all_in";

export interface LegalActions {
  actions: Action[];
  to_call: number;
  min_raise_to: number;
  max_raise_to: number;
  pot: number;
  current_bet: number;
  stack: number;
}

export interface PlayerPublic {
  seat: number;
  name: string;
  stack: number;
  is_human: boolean;
  profile: string;
  cards: string[] | null;
  bet_this_street: number;
  total_invested: number;
  folded: boolean;
  all_in: boolean;
  last_action: { type: string; amount: number } | null;
}

export interface StatePublic {
  street: string;
  board: string[];
  pot: number;
  current_bet: number;
  to_act_seat: number | null;
  button_seat: number;
  small_blind: number;
  big_blind: number;
  ante: number;
  players: PlayerPublic[];
  history: Array<{ street: string; seat: number; action: { type: string; amount: number } | null }>;
  winners: Array<{ seat: number; amount: number; reason: string }>;
}

export interface CoachFeedback {
  is_mistake: boolean;
  severity: "ok" | "minor" | "major" | "blunder";
  headline: string;
  detail: string;
  correct_action: string | null;
  correct_size_bb: number | null;
  metrics: Record<string, unknown>;
}

export interface SessionSnapshot {
  session_id: string;
  hand_no: number;
  level: { sb: number; bb: number; ante: number; minutes: number };
  level_index: number;
  tournament_players_alive: number;
  icm: Array<{ seat: number; name: string; stack: number; icm_equity: number }>;
  config: {
    structure: string;
    starting_stack: number;
    n_players: number;
    hero_seat: number;
    bot_profiles: string[];
    payouts: number[];
    coach_enabled: boolean;
  };
  table_players: Array<{
    seat: number;
    name: string;
    stack: number;
    is_human: boolean;
    profile: string;
    profile_label: string;
    alive: boolean;
  }>;
  state: StatePublic | null;
  legal_actions: LegalActions | null;
  last_coach: CoachFeedback | null;
  events_tail: Array<{ t: number; type: string; payload: unknown }>;
  hand_complete: boolean;
  tournament_over: boolean;
  ranking_when_busted: Array<{ seat: number; name: string }>;
}

export interface CreateSessionRequest {
  structure: "turbo" | "regular";
  starting_stack: number;
  n_players: number;
  hero_seat: number;
  bot_profiles: string[];
  payouts: number[];
  coach_enabled: boolean;
  coach_llm_enabled: boolean;
}
