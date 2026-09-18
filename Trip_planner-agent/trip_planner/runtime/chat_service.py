"""Multi-turn chat service over the Trip Guide agent."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from trip_planner.agents.trip_concierge import build_trip_guide
from trip_planner.config import APP_NAME, DEFAULT_USER_ID, model_candidates, require_api_key
from trip_planner.runtime.cards import begin_turn, end_turn

TOOL_STATUS_LABELS = {
    "publish_trip_board": "Updating trip board…",
    "publish_trip_prefs": "Saving preferences…",
    "weather_specialist": "Checking climate…",
    "places_specialist": "Searching places…",
    "stays_specialist": "Finding food & stays…",
    "get_weather_for_dates": "Checking climate…",
    "get_live_weather_forecast": "Checking weather…",
    "suggest_places": "Searching places…",
    "suggest_food": "Finding food spots…",
    "search_lodging": "Searching stays…",
    "get_directions": "Building map route…",
    "compound_research": "Researching with Groq Compound…",
    "web_search": "Searching the web…",
}

_TRANSIENT_MARKERS = (
    "503",
    "UNAVAILABLE",
    "429",
    "RESOURCE_EXHAUSTED",
    "HIGH DEMAND",
    "TEMPORARILY",
    "TRY AGAIN LATER",
    "OVERLOADED",
)

_UNAVAILABLE_MODEL_MARKERS = (
    "404",
    "NOT_FOUND",
    "MODEL_NOT_FOUND",
    "NO LONGER AVAILABLE",
    "IS NOT FOUND",
    "DOES NOT EXIST",
    "DO NOT HAVE ACCESS",
    "NOT AVAILABLE TO NEW USERS",
    "TOOL CALLING",
    "NOT SUPPORTED WITH THIS MODEL",
    "REASONING_CONTENT",
)

_FRIENDLY_BUSY = (
    "Gemini is busy right now (high demand). I tried again with backup models — "
    "please wait a few seconds and send your message once more."
)


def _is_transient_error(text: str) -> bool:
    upper = (text or "").upper()
    return any(marker in upper for marker in _TRANSIENT_MARKERS)


def _is_unavailable_model(text: str) -> bool:
    upper = (text or "").upper()
    return any(marker in upper for marker in _UNAVAILABLE_MODEL_MARKERS)


def _should_try_next_model(text: str) -> bool:
    return _is_transient_error(text) or _is_unavailable_model(text)


def _friendly_error(raw: str) -> str:
    upper = (raw or "").upper()
    if "RATE_LIMIT" in upper or "RATE LIMIT" in upper or "TOKENS PER MINUTE" in upper:
        return (
            "Groq rate limit hit for a moment. Wait ~30 seconds and send again — "
            "Trip Guide will keep using the specialist agents."
        )
    if _is_unavailable_model(raw):
        return (
            "That model isn’t available on your key (it may be retired). "
            "I tried the configured Gemini and Groq backups — please send your "
            "message once more, or set TRIP_PLANNER_MODEL / GROQ_MODEL in Settings."
        )
    if _is_transient_error(raw):
        return _FRIENDLY_BUSY
    cleaned = re.sub(r"^An error occurred:\s*", "", raw or "").strip()
    return cleaned or "Something went wrong. Please try again."


@dataclass
class ChatResult:
    session_id: str
    reply: str
    cards: list[dict[str, Any]] = field(default_factory=list)
    activity: list[str] = field(default_factory=list)


class ChatService:
    """Keeps ADK sessions alive so Trip Guide remembers the trip."""

    def __init__(self) -> None:
        self.session_service = InMemorySessionService()
        self.app_name = f"{APP_NAME}_guide"
        self._known_sessions: set[str] = set()
        self._runners: dict[str, Runner] = {}

    def _runner_for(self, model: str) -> Runner:
        if model not in self._runners:
            agent = build_trip_guide(model)
            self._runners[model] = Runner(
                agent=agent,
                session_service=self.session_service,
                app_name=self.app_name,
            )
        return self._runners[model]

    async def _ensure_session(self, session_id: str, user_id: str) -> str:
        if session_id in self._known_sessions:
            return session_id
        try:
            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            self._known_sessions.add(session.id)
            return session.id
        except Exception:
            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
            )
            self._known_sessions.add(session.id)
            return session.id

    async def chat_events(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield status/done events for streaming UI."""
        require_api_key()
        client_sid = session_id or str(uuid.uuid4())
        sid = await self._ensure_session(client_sid, user_id)

        begin_turn()
        reply = ""
        activity: list[str] = []
        last_error = ""
        models = model_candidates()

        yield {"type": "status", "label": "Thinking…", "session_id": client_sid}

        for index, model in enumerate(models):
            if index > 0:
                # Fresh ADK session so incomplete tool calls from a failed model
                # do not poison Groq Compound (Missing tool results…).
                sid = await self._ensure_session(str(uuid.uuid4()), user_id)
                label = (
                    f"Falling back to Groq ({model})…"
                    if str(model).startswith("groq/")
                    else f"Model busy — trying {model}…"
                )
                yield {
                    "type": "status",
                    "label": label,
                    "session_id": client_sid,
                }
                await asyncio.sleep(0.25 * index)

            runner = self._runner_for(model)
            attempt_reply = ""
            try:
                # One retry only for soft empty replies; hard 503/404 skip immediately
                max_attempts = 2
                for attempt in range(max_attempts):
                    if attempt > 0:
                        yield {
                            "type": "status",
                            "label": "Still busy — retrying…",
                            "session_id": client_sid,
                        }
                        await asyncio.sleep(0.8)

                    attempt_reply = ""
                    async for event in runner.run_async(
                        user_id=user_id,
                        session_id=sid,
                        new_message=Content(parts=[Part(text=message)], role="user"),
                    ):
                        for call in event.get_function_calls() or []:
                            name = getattr(call, "name", None) or ""
                            label = TOOL_STATUS_LABELS.get(
                                name, f"Using {name or 'tool'}…"
                            )
                            if label not in activity:
                                activity.append(label)
                            yield {
                                "type": "status",
                                "label": label,
                                "session_id": client_sid,
                            }

                        if event.is_final_response() and event.content and event.content.parts:
                            text = event.content.parts[0].text
                            if text:
                                attempt_reply = text

                    if attempt_reply and _should_try_next_model(attempt_reply):
                        last_error = attempt_reply
                        break  # next model; do not retry same id on 404/503 text
                    if attempt_reply:
                        reply = attempt_reply
                        break
                    last_error = "empty response"
                else:
                    if attempt_reply and not _should_try_next_model(attempt_reply):
                        reply = attempt_reply
                        break
                    continue

                if reply and not _should_try_next_model(reply):
                    break
            except Exception as e:
                last_error = str(e)
                if _should_try_next_model(last_error):
                    continue
                reply = _friendly_error(f"An error occurred: {e}")
                break

        if not reply:
            reply = _friendly_error(last_error or _FRIENDLY_BUSY)
        elif _should_try_next_model(reply):
            reply = _friendly_error(reply)

        cards = end_turn()
        yield {
            "type": "done",
            "session_id": client_sid,
            "reply": reply,
            "cards": cards,
            "activity": activity,
        }

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
    ) -> ChatResult:
        result = ChatResult(session_id=session_id or "", reply="", cards=[], activity=[])
        async for event in self.chat_events(message, session_id=session_id, user_id=user_id):
            if event.get("type") == "done":
                result = ChatResult(
                    session_id=event["session_id"],
                    reply=event.get("reply") or "",
                    cards=event.get("cards") or [],
                    activity=event.get("activity") or [],
                )
        return result


def sse_pack(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


# Process-wide service for the API
chat_service = ChatService()
