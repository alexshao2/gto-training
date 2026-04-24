"""FastAPI entrypoint for the Poker GTO Coach backend."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router


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

    app.include_router(router, prefix="/api")
    return app


app = create_app()
