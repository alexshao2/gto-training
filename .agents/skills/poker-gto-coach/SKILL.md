# Poker GTO Coach — development workflow

## Live deployments

- **Backend (Fly.io)**: https://poker-gto-coach-backe-irtmooox.fly.dev
  - `/health`, `/debug/env` (boolean presence check for env vars)
  - REST API at `/api/*`, WebSocket at `/ws/{session_id}`
- **Frontend (devinapps)**: https://dist-ltbgtirk.devinapps.com
  - Built artifact lives in `frontend/dist/`. Re-deploy via `deploy frontend dir=frontend/dist` after `npm run build`.

Deployment is via the Devin built-in `deploy` tool. The tool generates its own Dockerfile and ignores both the repo's `Dockerfile` and `[env]` section of `fly.toml`. Don't waste time editing those expecting the deploy tool to pick them up.

## Secrets handling

The Devin `deploy` tool does NOT inject env vars or read `flyctl secrets`. To ship secrets:

1. Put them in `backend/.env` (file is gitignored).
2. `app/main.py` runs `_load_dotenv_if_present()` at import time which loads `/app/.env` (the deployed copy of `backend/.env`) into `os.environ` without overwriting platform-set values.
3. Verify with `curl https://<backend>/debug/env` → returns booleans only.

For the user's custom LLM proxy (Vietnamese coach), the relevant env vars are:

- `OPENAI_API_KEY` — bearer token for the proxy
- `OPENAI_BASE_URL=https://r3klrij.9router.com/v1`
- `OPENAI_MODEL=Clawbot`

These are stored as the user-scoped secret `POKER_GTO_OPENAI_API_KEY` (URL + model are not secret and live in `backend/.env`).

## LLM endpoint quirks

The user's proxy `r3klrij.9router.com/v1` is OpenAI-compatible **but**:

1. It returns SSE-style streaming (`data: {...}\ndata: [DONE]`) even when `stream: false` is requested. `app/coach/llm.py::_parse_openai_response()` handles both plain JSON and SSE.
2. The backing model (`Clawbot` → minimax-m2.5) is reasoning-heavy. With small `max_tokens`, all completion tokens are consumed by reasoning and `message.content` is empty. We use `max_tokens=1500` and fall back to `message.reasoning` when `content` is empty.

If the user swaps in a different proxy, expect to need to re-verify both behaviors.

## Dev commands

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
ruff check app tests       # MUST be clean
python -m pytest tests/ -q # 9 tests, MUST pass
uvicorn app.main:app --reload --port 8080

# Frontend
cd frontend && npm install
npm run typecheck && npm run build
npm run dev                # http://localhost:5173
```

The frontend dev server reads `VITE_API_BASE` from `frontend/.env` (or `.env.production` for builds). Keep `.env.production` pointing at the deployed Fly.io URL so production builds talk to production backend.

## End-to-end smoke test

A full hand can be verified with curl in <1 minute:

```bash
BACKEND=https://poker-gto-coach-backe-irtmooox.fly.dev
curl -s -X POST $BACKEND/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"n_players":6,"starting_stack":10000,"coach_llm_enabled":true,"hero_seat":0}' \
  | jq '.session_id, .state.players[] | select(.is_human) | .cards'
# then POST /api/sessions/<id>/action with body {"action":"raise","amount":200}
# expect last_coach.detail to contain a substantial Vietnamese explanation when LLM key is set
```

## Repo layout

- `backend/app/poker/` — pure-Python NLHE engine (cards, evaluator, equity, state machine)
- `backend/app/bots/profiles.py` — 7 rule-based bot profiles
- `backend/app/coach/charts.py` — pre-solved RFI + vs-RFI ranges (6-max GTO Wizard approximation)
- `backend/app/coach/coach.py` — preflop chart lookup + postflop heuristic; emits `CoachFeedback`
- `backend/app/coach/llm.py` — optional Anthropic/OpenAI enrichment with SSE + reasoning fallback
- `backend/app/tournament/structure.py` — turbo/regular blind levels + Malmuth-Harville ICM
- `backend/app/api/{main,routes,session}.py` — FastAPI app, REST/WS routes, session manager
- `frontend/src/components/{Lobby,Table,ActionBar,CoachPanel,PlayerSeat,Card}.tsx`
- `frontend/src/store/session.ts` — Zustand store (snapshot, profiles, loading, error)
- `frontend/src/api/client.ts` — fetch helpers; reads `VITE_API_BASE`
- `frontend/src/utils/telegram.ts` — Telegram WebApp SDK init + haptic helpers

## Don'ts

- Don't push directly to `main` — the system has a hard guardrail. Use feature branches and PRs.
- Don't commit `backend/.env` or `backend/fly.toml` — both are gitignored. Use `backend/.env.example` and `backend/fly.toml.example` as templates.
- Don't assume the deploy tool's Dockerfile uses your `Dockerfile` or `fly.toml` — set env via `.env` and the dotenv loader instead.
- Don't expand `max_tokens` for the LLM coach indefinitely; reasoning models can chew through tokens. 1500 is the verified working value.
