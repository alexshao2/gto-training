# Poker GTO Coach — Telegram Bot Wrapper

Lightweight aiogram-3 bot that launches the Poker GTO Coach MiniApp from inside Telegram.

## Local run

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
export WEBAPP_URL=https://dist-ltbgtirk.devinapps.com
pip install "aiogram>=3.13.0"
python main.py
```

## Deploy to Fly.io

```bash
fly launch --no-deploy --copy-config        # answer yes to keep fly.toml
fly secrets set TELEGRAM_BOT_TOKEN=...       # required
fly deploy
```

## Commands

- `/start` — main menu with WebApp button + persistent reply keyboard
- `/play`  — quick link to open MiniApp
- `/help`  — usage guide

The bot also sets a persistent menu button (bottom-left of every chat) that opens
the MiniApp on tap, and registers `/start /play /help` in the Telegram command
list.
