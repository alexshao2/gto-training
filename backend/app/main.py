"""FastAPI entrypoint for the Poker GTO Coach backend."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router


def _load_dotenv_if_present() -> None:
    """Lightweight .env loader (so we don't need python-dotenv as a dep).

    Only sets keys that are NOT already present in the environment, so any
    secret manager or platform-level env wins.
    """
    for candidate in (Path("/app/.env"), Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
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
        except Exception:  # noqa: BLE001 - best-effort
            continue


_load_dotenv_if_present()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Poker GTO Coach",
        version="0.1.0",
        description="Telegram MiniApp backend for realtime poker GTO training.",
    )
    origins = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174,https://web.telegram.org",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins + ["*"],  # Permissive for MVP; tighten in prod
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok", "service": "poker-gto-coach"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/debug/env")
    async def debug_env() -> dict[str, bool | str]:
        """Boolean presence check for optional env vars. Never returns values."""
        return {
            "has_anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "has_openai_key": bool(os.environ.get("OPENAI_API_KEY")),
            "openai_base_url_set": bool(os.environ.get("OPENAI_BASE_URL")),
            "openai_model_set": bool(os.environ.get("OPENAI_MODEL")),
        }

    app.include_router(router, prefix="/api")
    return app


app = create_app()
