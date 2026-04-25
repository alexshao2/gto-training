"""Telegram bot wrapper for the Poker GTO Coach MiniApp.

Runs as a FastAPI webhook on Fly.io. Provides /start, /play, /help and a
persistent menu button that launches the MiniApp web view inside Telegram.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path


def _load_dotenv_if_present() -> None:
    """Lightweight .env loader. Platform env vars always win."""
    for candidate in (Path("/app/.env"), Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"):
        if not candidate.is_file():
            continue
        try:
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except Exception:  # noqa: BLE001
            continue


_load_dotenv_if_present()

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from fastapi import FastAPI, HTTPException, Request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("poker-gto-bot")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://dist-ltbgtirk.devinapps.com").strip()
# Public URL of THIS bot service (set by Fly secrets after first deploy).
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").strip()
# Random path segment so only Telegram can call our webhook.
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "tg-hook").strip()

if not BOT_TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN env var is required")


WELCOME_VI = (
    "<b>♠ Poker GTO Coach ♥</b>\n\n"
    "Train MTT 6-max với AI bots cấp độ thực + HLV GTO realtime.\n\n"
    "Bấm nút <b>🎯 Train</b> bên dưới (hoặc nút Menu góc dưới-trái) để mở MiniApp."
)

HELP_VI = (
    "<b>Hướng dẫn nhanh</b>\n\n"
    "1) Lobby: chọn cấu trúc (Turbo/Regular), stack, số player, profile bot, bật coach.\n"
    "2) Bấm <b>Bắt đầu giải đấu</b> để vào bàn 6-max.\n"
    "3) Quyết định ở mỗi spot. Coach sẽ flag ngay khi bạn lệch khỏi GTO.\n"
    "4) Hand auto-deal sau showdown. Game dừng khi bạn out hoặc thắng giải.\n\n"
    "Lệnh:\n"
    "/start — mở menu chính\n"
    "/play — mở MiniApp\n"
    "/help — xem hướng dẫn này"
)


def build_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎯 Train (mở MiniApp)",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ],
            [InlineKeyboardButton(text="📘 Hướng dẫn", callback_data="help")],
        ]
    )


def build_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎯 Train", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
        is_persistent=True,
    )


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


@dp.message(CommandStart())
async def on_start(message: types.Message) -> None:
    log.info("/start from user_id=%s", message.from_user.id if message.from_user else "?")
    await message.answer(WELCOME_VI, reply_markup=build_reply_keyboard())
    await message.answer(
        "Hoặc bấm nút bên dưới để mở MiniApp ngay:",
        reply_markup=build_inline_keyboard(),
    )


@dp.message(Command("play"))
async def on_play(message: types.Message) -> None:
    await message.answer("Bấm nút <b>🎯 Train</b> để mở MiniApp:", reply_markup=build_inline_keyboard())


@dp.message(Command("help"))
async def on_help(message: types.Message) -> None:
    await message.answer(HELP_VI, reply_markup=build_inline_keyboard())


@dp.callback_query(F.data == "help")
async def on_help_cb(callback: types.CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer(HELP_VI, reply_markup=build_inline_keyboard())
    await callback.answer()


@dp.message(F.web_app_data)
async def on_webapp_data(message: types.Message) -> None:
    """Receives data sent from the MiniApp via Telegram.WebApp.sendData()."""
    payload = message.web_app_data.data if message.web_app_data else ""
    log.info("webapp_data from %s: %s", message.from_user.id if message.from_user else "?", payload)
    await message.answer("Đã nhận dữ liệu từ MiniApp.")


async def setup_bot_commands_and_menu() -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Mở menu chính"),
            BotCommand(command="play", description="Vào MiniApp ngay"),
            BotCommand(command="help", description="Hướng dẫn sử dụng"),
        ]
    )
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="🎯 Train", web_app=WebAppInfo(url=WEBAPP_URL))
    )
    try:
        await bot.set_my_description(
            description="Train MTT 6-max poker với AI bots + HLV GTO realtime. Bấm Menu để mở MiniApp."
        )
        await bot.set_my_short_description(
            short_description="Poker GTO Coach — train MTT realtime với AI bots."
        )
    except Exception as e:
        log.warning("set_my_description failed (non-fatal): %s", e)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    me = await bot.get_me()
    log.info("Logged in as @%s (id=%s)", me.username, me.id)
    await setup_bot_commands_and_menu()

    if PUBLIC_URL:
        webhook_url = f"{PUBLIC_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"
        try:
            current = await bot.get_webhook_info()
            if current.url != webhook_url:
                await bot.set_webhook(
                    url=webhook_url,
                    drop_pending_updates=True,
                    allowed_updates=["message", "callback_query"],
                )
                log.info("Webhook set to %s", webhook_url)
            else:
                log.info("Webhook already correct: %s", webhook_url)
        except Exception as e:
            log.error("Failed to set webhook: %s", e)
    else:
        log.warning("PUBLIC_URL not set — webhook NOT configured. Set fly secret PUBLIC_URL=https://<app>.fly.dev")

    yield

    try:
        await bot.session.close()
    except Exception:
        pass


app = FastAPI(title="Poker GTO Coach Bot", lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "ok", "bot": True}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug/env")
async def debug_env():
    return {
        "has_token": bool(BOT_TOKEN),
        "webapp_url": WEBAPP_URL,
        "public_url_set": bool(PUBLIC_URL),
    }


@app.post("/webhook/{secret}")
async def webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}
