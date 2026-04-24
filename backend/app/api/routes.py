"""HTTP + WebSocket routes."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..bots.profiles import PROFILE_LABELS
from .session import (
    SESSIONS,
    TournamentConfig,
    create_session,
    get_session,
)

router = APIRouter()


class CreateSessionRequest(BaseModel):
    structure: str = Field("turbo", description="turbo | regular")
    starting_stack: int = 10000
    n_players: int = Field(6, ge=2, le=9)
    hero_seat: int = 0
    bot_profiles: list[str] = Field(
        default_factory=lambda: ["tag", "lag", "fish", "nit", "gto"]
    )
    payouts: list[float] = Field(default_factory=lambda: [50.0, 30.0, 20.0])
    coach_enabled: bool = True
    coach_llm_enabled: bool = True


class HeroActionRequest(BaseModel):
    action: str  # fold | check | call | bet | raise | all_in
    amount: int = 0


@router.get("/profiles")
async def list_profiles() -> dict[str, str]:
    return PROFILE_LABELS


@router.get("/structures")
async def list_structures() -> list[str]:
    return ["turbo", "regular"]


@router.post("/sessions")
async def create_session_endpoint(req: CreateSessionRequest) -> dict[str, Any]:
    cfg = TournamentConfig(
        structure=req.structure,
        starting_stack=req.starting_stack,
        n_players=req.n_players,
        hero_seat=req.hero_seat,
        bot_profiles=req.bot_profiles,
        payouts=req.payouts,
        coach_enabled=req.coach_enabled,
        coach_llm_enabled=req.coach_llm_enabled,
    )
    session = create_session(cfg)
    session.start_new_hand()
    snap = await session.step_bots()
    return snap


@router.get("/sessions/{session_id}")
async def get_session_snapshot(session_id: str) -> dict[str, Any]:
    try:
        session = get_session(session_id)
    except KeyError:
        raise HTTPException(404, "Session not found")
    return session.snapshot()


@router.post("/sessions/{session_id}/action")
async def submit_action(session_id: str, req: HeroActionRequest) -> dict[str, Any]:
    try:
        session = get_session(session_id)
    except KeyError:
        raise HTTPException(404, "Session not found")
    async with session.lock:
        try:
            snap = await session.submit_hero_action(req.action, req.amount)
        except (RuntimeError, ValueError) as e:
            raise HTTPException(400, str(e))
        # Drive bots until hero turn or completion
        snap = await session.step_bots()
        if session.state and session.state.street.value == "complete":
            # Auto-deal next hand if tournament still alive
            alive = [p for p in session.players if p.stack > 0]
            if len(alive) >= 2:
                session.start_new_hand()
                snap = await session.step_bots()
    return snap


@router.post("/sessions/{session_id}/next_hand")
async def next_hand(session_id: str) -> dict[str, Any]:
    try:
        session = get_session(session_id)
    except KeyError:
        raise HTTPException(404, "Session not found")
    session.start_new_hand()
    snap = await session.step_bots()
    return snap


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    SESSIONS.pop(session_id, None)
    return {"status": "deleted"}


# ---- WebSocket ----
class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.setdefault(session_id, []).append(ws)

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        conns = self.connections.get(session_id, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, session_id: str, message: dict) -> None:
        conns = list(self.connections.get(session_id, []))
        for ws in conns:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                self.disconnect(session_id, ws)


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    try:
        session = get_session(session_id)
    except KeyError:
        await websocket.close(code=4404)
        return
    await manager.connect(session_id, websocket)
    try:
        # Send initial snapshot
        await websocket.send_text(json.dumps({"type": "snapshot", "data": session.snapshot()}))
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "action":
                async with session.lock:
                    try:
                        snap = await session.submit_hero_action(
                            msg.get("action", "fold"), int(msg.get("amount", 0))
                        )
                        await manager.broadcast(session_id, {"type": "snapshot", "data": snap})
                        snap = await session.step_bots()
                        await manager.broadcast(session_id, {"type": "snapshot", "data": snap})
                        if session.state and session.state.street.value == "complete":
                            alive = [p for p in session.players if p.stack > 0]
                            if len(alive) >= 2:
                                await asyncio.sleep(1.0)
                                session.start_new_hand()
                                snap = await session.step_bots()
                                await manager.broadcast(session_id, {"type": "snapshot", "data": snap})
                    except Exception as e:
                        await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
            elif msg.get("type") == "next_hand":
                async with session.lock:
                    session.start_new_hand()
                    snap = await session.step_bots()
                    await manager.broadcast(session_id, {"type": "snapshot", "data": snap})
            elif msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)



