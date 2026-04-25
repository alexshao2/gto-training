# Poker GTO Coach — Telegram MiniApp

Một Telegram MiniApp huấn luyện poker MTT/cash 6-max **thực chiến** với:

- **AI bots** đóng vai opponent với nhiều profile (Nit / Rock / TAG / LAG / Fish / Maniac / GTO).
- **Tournament engine** đầy đủ: blind structure (turbo / regular), ante, ICM equity tính theo Malmuth-Harville.
- **GTO Coach realtime** — phát hiện sai lầm khỏi solver line ngay lập tức và giải thích vì sao sai theo logic GTO (range, equity, EV, blockers, board texture, pot odds, SPR…).
- **LLM-enriched feedback** (optional): khi cấu hình `OPENAI_API_KEY` hoặc `ANTHROPIC_API_KEY`, coach trả về giải thích sâu hơn bằng tiếng Việt.

> MVP: pre-solved preflop charts (RFI + vs RFI cho hầu hết match-up 6-max) + post-flop heuristic dựa trên equity Monte-Carlo, hand strength, board texture, pot odds. Không phải solver thật, nhưng đã đủ để bắt 80%+ leak phổ biến của mid-stakes.

## Stack

- **Frontend**: React 18 + TypeScript + Vite + Zustand + Telegram WebApp SDK → Vercel.
- **Backend**: Python 3.11 + FastAPI + WebSocket → Fly.io (Docker).
- **Engine** (Python): `app/poker` — cards, deck, evaluator, equity, hand state machine.
- **Bots**: `app/bots/profiles.py` — rule-based, mỗi profile có aggression / bluff / looseness / skill.
- **Coach**: `app/coach` — preflop charts, post-flop heuristic, optional LLM enrichment.
- **Tournament**: `app/tournament/structure.py` — blind levels + ICM.

## Cấu trúc thư mục

```
poker-gto-coach/
├── backend/
│   ├── app/
│   │   ├── poker/         # cards, deck, evaluator, equity, state machine
│   │   ├── bots/          # AI player profiles
│   │   ├── coach/         # GTO charts + heuristic + LLM
│   │   ├── tournament/    # blind structure + ICM
│   │   ├── api/           # FastAPI routes + WebSocket + session manager
│   │   └── main.py
│   ├── tests/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── fly.toml
└── frontend/
    ├── src/
    │   ├── components/    # Card, PlayerSeat, ActionBar, CoachPanel, Lobby, Table
    │   ├── api/           # REST client
    │   ├── store/         # Zustand session store
    │   ├── types/
    │   ├── utils/telegram.ts
    │   ├── App.tsx
    │   └── main.tsx
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    └── vite.config.ts
```

## Local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check app tests

# Run server
uvicorn app.main:app --reload --port 8080
```

Optional environment variables:

- `ANTHROPIC_API_KEY` (recommended) hoặc `OPENAI_API_KEY` — để bật LLM coach.
- `ANTHROPIC_MODEL` (default `claude-3-5-haiku-20241022`).
- `OPENAI_MODEL` (default `gpt-4o-mini`).
- `OPENAI_BASE_URL` (default `https://api.openai.com/v1`) — đổi để dùng custom OpenAI-compatible endpoint (ví dụ proxy nội bộ).
- `CORS_ORIGINS` — danh sách origin phân tách bằng dấu phẩy.

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
npm run build
```

Cấu hình API base qua biến môi trường Vite:

```bash
VITE_API_BASE=https://poker-gto-coach.fly.dev npm run build
```

## Self-host local + Cloudflare Tunnel

Chạy toàn bộ stack (backend + frontend + bot Telegram) trên máy local và public ra internet qua **một Cloudflare Tunnel duy nhất** — không cần domain riêng cho từng service, không cần CORS config.

### Kiến trúc

```
Internet ─▶ Cloudflare ─▶ cloudflared (sidecar) ─┐
                                                  ▼
                                            ┌────────────┐
                                            │  frontend  │  ← nginx serve SPA + reverse proxy
                                            └─────┬──────┘
                                                  │
                          /api, /api/ws    ┌──────┴──────┐    /tg/webhook/<secret>
                                  ▼        │             │             ▼
                           ┌──────────┐    │             │    ┌──────────────┐
                           │ backend  │    │             │    │   bot (TG)   │
                           │ FastAPI  │    │             │    │  webhook app │
                           └──────────┘    │             │    └──────────────┘
                                            └─────────────┘
```

Một domain phục vụ tất cả: SPA, REST `/api`, WebSocket `/api/ws/*`, Telegram webhook `/tg/webhook/<secret>`.

### Yêu cầu

- Docker + Docker Compose v2.
- Cloudflare Zero Trust account (free tier OK), 1 domain đã add vào Cloudflare.
- Cloudflare Tunnel **token** (dạng `eyJh…` rất dài).

### Bước 1 — Setup Cloudflare Tunnel

1. Vào [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com/) → **Networks → Tunnels** → **Create a tunnel** → **Cloudflared**.
2. Đặt tên (vd `poker-gto-coach`), chọn **Save tunnel**, ở bước "Install connector" copy token (đoạn dài sau `--token`). Token sẽ là `TUNNEL_TOKEN` ở bước 2.
3. Tab **Public Hostnames** → **Add a public hostname**:
   - Subdomain + Domain: ví dụ `poker.your-domain.com`.
   - Service: `HTTP`, URL: `frontend:80` (chính là tên container nginx — cloudflared chạy cùng docker network nên resolve được).
   - Save hostname.

### Bước 2 — Tạo các file `.env`

```bash
cp backend/.env.example backend/.env
# điền OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, TTS_MODEL, ...

cp bot/.env.example bot/.env
# - TELEGRAM_BOT_TOKEN  (từ @BotFather)
# - WEBAPP_URL=https://poker.your-domain.com/        ← URL public của bạn
# - PUBLIC_URL=https://poker.your-domain.com/tg      ← chú ý hậu tố `/tg`
# - WEBHOOK_SECRET=<random-string>

cp .env.example .env
# - TUNNEL_TOKEN=eyJh...   (token bước 1)
```

### Bước 3 — Chạy

```bash
docker compose up -d --build
```

Đợi vài giây rồi kiểm tra:

```bash
curl https://poker.your-domain.com/api/profiles      # JSON danh sách bot profiles
curl https://poker.your-domain.com/                  # SPA index.html
docker compose logs -f cloudflared                   # xem connector status
docker compose logs -f bot                           # bot phải log "Webhook set to https://poker.../tg/webhook/<secret>"
```

Mở https://poker.your-domain.com/ trên trình duyệt → MiniApp lên. Hoặc vào @BotFather → `/setmenubutton` → trỏ vào WEBAPP_URL.

### Bước 4 — Cập nhật

```bash
git pull
docker compose up -d --build
```

### Lưu ý

- `frontend` được build với `VITE_API_BASE=""` để dùng same-origin paths → KHÔNG cần config CORS riêng.
- Chỉ cloudflared mở ra internet — backend, bot, và nginx đều `expose:` chứ không `ports:` → các service nội bộ KHÔNG bị publish ra interface công cộng.
- Webhook bot dùng path prefix `/tg` để chia sẻ cùng domain với SPA và `/api`. Nếu bạn muốn 2 domain riêng (`bot.your-domain.com` cho Telegram), thêm 1 Public Hostname nữa trong CF Tunnel trỏ thẳng vào `bot:8080`, đổi `PUBLIC_URL=https://bot.your-domain.com` và bỏ phần `/tg/` proxy trong `frontend/nginx.conf`.

## Deploy (legacy, Fly.io + Vercel)

### Backend → Fly.io

```bash
cd backend
flyctl launch --no-deploy   # accept generated config or use fly.toml
flyctl secrets set ANTHROPIC_API_KEY=sk-ant-...
flyctl deploy
```

### Frontend → Vercel

```bash
cd frontend
# Hoặc qua Vercel dashboard, hoặc:
vercel --prod
# Set VITE_API_BASE = https://<your-fly-app>.fly.dev trong project env
```

## Telegram MiniApp setup

1. Mở chat với [@BotFather](https://t.me/BotFather) → `/newbot` → nhận **bot token**.
2. `/newapp` → chọn bot vừa tạo → nhập **Web App URL** = URL Vercel của frontend.
3. Trong code bot (Python/Node bất kỳ), gắn nút launch:
   ```
   InlineKeyboardButton(text="🃏 Train Poker", web_app=WebAppInfo(url="https://<vercel-url>"))
   ```
4. Người dùng bấm → MiniApp mở trong Telegram, tự động dùng theme tương ứng.

## Coach logic — sơ lược

### Preflop

- **RFI**: đối chiếu hand combo của hero với chart RFI cho vị trí. Sai = fold-hand-trong-range hoặc raise-hand-out-of-range.
- **vs RFI**: lookup `(hero_pos, villain_pos) → {3bet_set, call_set}`. Phân loại blunder/major/minor theo độ nặng (vd fold AKs vs CO open = blunder).

### Postflop

Tính:
- `equity = MonteCarlo(hero_hand, board, iters=300)` vs random villain.
- `pot_odds = to_call / (pot + to_call)`.
- `spr = stack / pot`.
- `board_texture` (wet/dry, monotone, paired, connected).
- `hand_strength` (category từ evaluator).

Quy tắc mẫu:
- `fold` khi `equity > pot_odds + 10%` và có ít nhất pair → flag **major leak**.
- `call` khi `equity < pot_odds - 5%` và high card → flag **major leak**.
- `check` với strong made hand trên wet board → flag slowplay danger.
- `raise` không equity, không blocker → flag spew bluff.

### Optional LLM

Khi flag mistake, gửi state + metrics tới Claude/GPT với prompt tiếng Việt → trả lại giải thích in-context (range, blocker, ICM nếu có…). Fallback nếu không có API key.

## Test cases được phủ

```bash
backend/tests/test_engine.py
  test_card_basics
  test_deck_unique
  test_evaluator_flush_beats_straight
  test_evaluator_full_house_beats_flush
  test_quads_beats_full_house
  test_evaluate_best_7_cards
  test_combo_string
  test_full_hand_runs_to_completion
  test_coach_flags_premium_fold_preflop
```

## Roadmap (post-MVP)

- [ ] Real solver integration (CFR via OpenSpiel hoặc external API).
- [ ] Multi-table tournament (cho phép user ngồi nhiều bàn).
- [ ] Hand history replay với annotation chi tiết.
- [ ] Range visualizer (paint chart, mixed strategy frequencies).
- [ ] ICM-aware coaching ở final table (push/fold chart, bubble factor).
- [ ] User stat tracking (VPIP, PFR, AF…) + leak summary cuối phiên.
- [ ] Multilingual coach (English / Vietnamese / Chinese).
- [ ] Persistence (Postgres) cho hand history + cross-session leak tracking.

## License

MIT.
