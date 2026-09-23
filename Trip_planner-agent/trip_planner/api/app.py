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
from trip_planner.tools.geocode import geocode_place
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
    ollama_api_base: str | None = None
    ollama_model: str | None = None
    ollama_model_fallbacks: str | None = None
    runtime_mode: str | None = None


class StopIn(BaseModel):
    name: str
    lat: float | None = None
    lon: float | None = None
    label: str | None = None


class GeometryRequest(BaseModel):
    stops: list[StopIn] = Field(default_factory=list)


class GeocodePlacesRequest(BaseModel):
    names: list[str] = Field(default_factory=list, max_length=12)


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
            and body.ollama_api_base is None
            and body.ollama_model is None
            and body.ollama_model_fallbacks is None
            and body.runtime_mode is None
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Provide google_api_key, google_maps_api_key, groq_api_key, "
                    "Ollama fields, and/or runtime_mode."
                ),
            )
        return save_api_keys(
            google_api_key=body.google_api_key,
            google_maps_api_key=body.google_maps_api_key,
            groq_api_key=body.groq_api_key,
            ollama_api_base=body.ollama_api_base,
            ollama_model=body.ollama_model,
            ollama_model_fallbacks=body.ollama_model_fallbacks,
            runtime_mode=body.runtime_mode,
        )

    @app.post("/api/trip/geometry")
    async def trip_geometry(body: GeometryRequest) -> dict[str, Any]:
        stops = [s.model_dump() for s in body.stops]
        return build_trip_geometry(stops)

    @app.post("/api/geocode/places")
    async def geocode_places(body: GeocodePlacesRequest) -> dict[str, Any]:
        """Geocode place titles for map pins (Open-Meteo, free)."""
        import re

        out: list[dict[str, Any]] = []
        seen: set[str] = set()

        def _candidates(title: str) -> list[str]:
            clean = title.split(" - ")[0].split(" | ")[0].strip()
            clean = re.sub(
                r"^\d+\s*(best|top|great)?\s*", "", clean, flags=re.I
            ).strip()
            parts = [p for p in re.split(r"[\s,|/]+", clean) if p]
            cands = [clean[:80]]
            if len(parts) >= 2:
                cands.append(parts[-1])
                cands.append(" ".join(parts[-2:]))
            if len(parts) >= 1:
                cands.append(parts[0])
            for hub in (
                "Gokarna",
                "Murudeshwar",
                "Murdeshwar",
                "Dandeli",
                "Bengaluru",
                "Bangalore",
                "Jog",
            ):
                if hub.lower() in clean.lower():
                    cands.insert(0, hub)
            seen_c: set[str] = set()
            uniq: list[str] = []
            for c in cands:
                k = c.lower()
                if k and k not in seen_c:
                    seen_c.add(k)
                    uniq.append(c)
            return uniq

        for raw in body.names[:12]:
            name = (raw or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            geo = None
            for cand in _candidates(name):
                geo = geocode_place(cand)
                if geo:
                    break
            if not geo:
                continue
            out.append(
                {
                    "query": name,
                    "name": geo.get("name") or name,
                    "lat": geo["latitude"],
                    "lon": geo["longitude"],
                    "admin1": geo.get("admin1") or "",
                    "country": geo.get("country") or "",
                }
            )
        return {"places": out}

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

    @app.post("/api/chat/stop")
    async def chat_stop(body: dict[str, Any]) -> dict[str, Any]:
        sid = (body or {}).get("session_id") or ""
        if not sid:
            raise HTTPException(status_code=400, detail="session_id required")
        chat_service.request_cancel(str(sid))
        return {"status": "ok", "session_id": sid}

    @app.post("/api/chat/stream")
    async def chat_stream(body: ChatRequest) -> StreamingResponse:
        try:
            require_api_key()
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        async def event_gen():
            sid = body.session_id or ""
            try:
                async for event in chat_service.chat_events(
                    message=body.message,
                    session_id=body.session_id,
                    user_id=body.user_id or "web_user",
                    trip_context=body.trip_context,
                ):
                    if event.get("session_id"):
                        sid = event["session_id"]
                    yield sse_pack(event)
            except Exception as e:
                # Never leave the ASGI stream half-open (browser → "network error")
                yield sse_pack(
                    {
                        "type": "done",
                        "session_id": sid,
                        "reply": (
                            "Something went wrong mid-trip. "
                            f"({type(e).__name__}: {e}). Try sending again."
                        ),
                        "cards": [],
                        "activity": [],
                    }
                )

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
