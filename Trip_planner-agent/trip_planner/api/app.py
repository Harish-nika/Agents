"""FastAPI chat API for Trip Guide."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from trip_planner.config import require_api_key
from trip_planner.runtime.chat_service import chat_service, sse_pack
from trip_planner.settings_store import save_api_keys, settings_status
from trip_planner.tools.route_geometry import build_trip_geometry

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    user_id: str | None = None
    trip_context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    cards: list[dict[str, Any]] = Field(default_factory=list)
    activity: list[str] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    google_api_key: str | None = None
    google_maps_api_key: str | None = None
    groq_api_key: str | None = None


class StopIn(BaseModel):
    name: str
    lat: float | None = None
    lon: float | None = None
    label: str | None = None


class GeometryRequest(BaseModel):
    stops: list[StopIn] = Field(default_factory=list)


def create_app() -> FastAPI:
    app = FastAPI(title="Trip Guide", version="0.4.0")

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        status = settings_status()
        return {"status": "ok", **status}

    @app.get("/api/settings")
    async def get_settings() -> dict[str, Any]:
        return settings_status()

    @app.post("/api/settings")
    async def update_settings(body: SettingsUpdate) -> dict[str, Any]:
        if (
            body.google_api_key is None
            and body.google_maps_api_key is None
            and body.groq_api_key is None
        ):
            raise HTTPException(
                status_code=400,
                detail="Provide google_api_key, google_maps_api_key, and/or groq_api_key.",
            )
        return save_api_keys(
            google_api_key=body.google_api_key,
            google_maps_api_key=body.google_maps_api_key,
            groq_api_key=body.groq_api_key,
        )

    @app.post("/api/trip/geometry")
    async def trip_geometry(body: GeometryRequest) -> dict[str, Any]:
        stops = [s.model_dump() for s in body.stops]
        return build_trip_geometry(stops)

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest) -> ChatResponse:
        try:
            require_api_key()
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        result = await chat_service.chat(
            message=body.message,
            session_id=body.session_id,
            user_id=body.user_id or "web_user",
            trip_context=body.trip_context,
        )
        return ChatResponse(
            session_id=result.session_id,
            reply=result.reply,
            cards=result.cards,
            activity=result.activity,
        )

    @app.post("/api/chat/stream")
    async def chat_stream(body: ChatRequest) -> StreamingResponse:
        try:
            require_api_key()
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        async def event_gen():
            async for event in chat_service.chat_events(
                message=body.message,
                session_id=body.session_id,
                user_id=body.user_id or "web_user",
                trip_context=body.trip_context,
            ):
                yield sse_pack(event)

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    if WEB_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(WEB_DIR / "index.html")

    return app


app = create_app()
