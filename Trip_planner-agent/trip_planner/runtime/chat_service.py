"""Multi-turn chat service over the Trip Guide agent."""

from __future__ import annotations

import asyncio
import json
import os
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
    "directions_specialist": "Planning route…",
    "get_weather_for_dates": "Checking climate…",
    "get_live_weather_forecast": "Checking weather…",
    "suggest_places": "Searching places…",
    "suggest_food": "Finding food spots…",
    "search_lodging": "Searching stays…",
    "get_directions": "Planning route…",
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
    "QUOTA",
    "RATE_LIMIT",
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

# Cap how long we wait on one model before trying the next (Gemini free-tier
# can sit in ADK/tenacity retries for many minutes otherwise).
_MODEL_ATTEMPT_TIMEOUT_S = float(os.getenv("TRIP_PLANNER_MODEL_TIMEOUT_S", "50"))


def _is_transient_error(text: str) -> bool:
    upper = (text or "").upper()
    return any(marker in upper for marker in _TRANSIENT_MARKERS)


def _is_unavailable_model(text: str) -> bool:
    upper = (text or "").upper()
    return any(marker in upper for marker in _UNAVAILABLE_MODEL_MARKERS)


def _is_quota_error(text: str) -> bool:
    upper = (text or "").upper()
    return any(
        m in upper
        for m in (
            "RESOURCE_EXHAUSTED",
            "QUOTA EXCEEDED",
            "EXCEEDED YOUR CURRENT QUOTA",
            "FREE_TIER",
            "GENERATE_CONTENT_FREE_TIER",
        )
    )


def _should_try_next_model(text: str) -> bool:
    return _is_transient_error(text) or _is_unavailable_model(text)


def _friendly_error(raw: str) -> str:
    upper = (raw or "").upper()
    if _is_quota_error(raw):
        return (
            "Gemini free-tier quota is used up for today (multi-agent turns burn "
            "several requests each). Wait for reset, or rely on Groq fallback "
            "(grok_key) — then send your message again."
        )
    if "RATE_LIMIT" in upper or "RATE LIMIT" in upper or "TOKENS PER MINUTE" in upper:
        return (
            "Groq rate limit hit for a moment. Wait ~30 seconds and send again — "
            "Trip Guide will keep using the specialist agents."
        )
    if "TIMEOUT" in upper:
        return (
            "A model took too long to respond, so I stopped waiting. "
            "Please send your message once more (Groq may pick up if Gemini is slow)."
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


_COT_MARKERS = (
    "the instructions say",
    "we need to understand the trip first",
    "likely they forgot",
    "so we need to ask",
    "chain of thought",
    "let me think",
    "my reasoning",
    "looking at the prompt",
    "so sequence:",
    "let's construct",
    "lets construct",
    "we'll call each",
    "provide request strings",
    "function calls",
)


def _looks_like_tool_planning_leak(text: str) -> bool:
    """True when the model narrates tool calls instead of invoking them."""
    lower = (text or "").lower()
    if not lower:
        return False
    if any(m in lower for m in _COT_MARKERS):
        return True
    tool_names = (
        "publish_trip_board",
        "publish_trip_prefs",
        "weather_specialist",
        "places_specialist",
        "stays_specialist",
        "directions_specialist",
    )
    hits = sum(1 for t in tool_names if t in lower)
    if hits >= 2:
        return True
    if "call `" in lower and "specialist" in lower:
        return True
    return False


def _format_trip_context(ctx: dict[str, Any] | None) -> str:
    """Compact board snapshot so the model sees UI trip state after server restarts."""
    if not ctx or not isinstance(ctx, dict):
        return ""
    stops = ctx.get("route_stops") or ctx.get("stops") or []
    if isinstance(stops, str):
        stops = [s.strip() for s in stops.split(",") if s.strip()]
    prefs = ctx.get("prefs") or {}
    bits = []
    origin = (ctx.get("origin") or "").strip()
    if origin:
        bits.append(f"origin={origin}")
    if stops:
        bits.append("stops=" + " → ".join(str(s) for s in stops))
    start = (ctx.get("start_date") or "").strip()
    end = (ctx.get("end_date") or "").strip()
    if start or end:
        bits.append(f"dates={start or '?'} → {end or '?'}")
    pref_bits = [
        prefs.get("budget"),
        prefs.get("pace"),
        prefs.get("vibe"),
        prefs.get("companions"),
    ]
    interests = prefs.get("interests") or []
    if isinstance(interests, list) and interests:
        pref_bits.append(", ".join(str(i) for i in interests))
    pref_bits = [p for p in pref_bits if p]
    if pref_bits:
        bits.append("prefs=" + "; ".join(str(p) for p in pref_bits))
    if not bits:
        return ""
    return (
        "[Current trip board — already shown in the UI; do not re-ask for these details]\n"
        + "\n".join(f"- {b}" for b in bits)
        + "\n\n"
    )


def _strip_chain_of_thought(text: str) -> str:
    """Drop leaked planning monologues; keep the last user-facing section if possible."""
    raw = (text or "").strip()
    if not raw:
        return raw
    lower = raw.lower()
    looks_like_cot = any(m in lower for m in _COT_MARKERS) or (
        lower.startswith("the user") and "we need" in lower
    )
    if not looks_like_cot:
        return raw

    # Prefer text after a clear reply marker
    for sep in ("\n\nSure", "\nSure!", "\nHere's", "\nHere is", "\n**", "\n#"):
        idx = raw.find(sep)
        if idx > 40:
            cleaned = raw[idx:].lstrip()
            if len(cleaned) > 20:
                return cleaned

    lines = raw.splitlines()
    kept: list[str] = []
    for line in lines:
        l = line.lower().strip()
        if any(m in l for m in _COT_MARKERS):
            continue
        if l.startswith("the user ") or l.startswith("they didn't") or l.startswith("we should ask"):
            continue
        if "instructions say" in l:
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    if cleaned and len(cleaned) > 30:
        return cleaned
    return (
        "Got it — using your current trip board. "
        "Ask me again for weather, places, or food and I’ll pull those via the specialists."
    )


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
        trip_context: dict[str, Any] | None = None,
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
        skip_remaining_gemini = False
        agent_message = f"{_format_trip_context(trip_context)}{message}"

        yield {"type": "status", "label": "Thinking…", "session_id": client_sid}

        for index, model in enumerate(models):
            is_groq = str(model).startswith("groq/")
            if skip_remaining_gemini and not is_groq:
                continue

            if index > 0 or skip_remaining_gemini:
                sid = await self._ensure_session(str(uuid.uuid4()), user_id)
                label = (
                    f"Falling back to Groq ({model})…"
                    if is_groq
                    else f"Model busy — trying {model}…"
                )
                yield {
                    "type": "status",
                    "label": label,
                    "session_id": client_sid,
                }
                await asyncio.sleep(0.1)

            runner = self._runner_for(model)
            attempt_reply = ""
            pending_status: list[str] = []
            yield {
                "type": "status",
                "label": f"Running {model}…",
                "session_id": client_sid,
            }

            async def _run_once() -> str:
                text_out = ""
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=sid,
                    new_message=Content(parts=[Part(text=agent_message)], role="user"),
                ):
                    for call in event.get_function_calls() or []:
                        name = getattr(call, "name", None) or ""
                        label = TOOL_STATUS_LABELS.get(
                            name, f"Using {name or 'tool'}…"
                        )
                        if label not in activity:
                            activity.append(label)
                        pending_status.append(label)
                    if (
                        event.is_final_response()
                        and event.content
                        and event.content.parts
                    ):
                        text = event.content.parts[0].text
                        if text:
                            text_out = text
                return text_out

            try:
                attempt_reply = await asyncio.wait_for(
                    _run_once(), timeout=_MODEL_ATTEMPT_TIMEOUT_S
                )
                for label in pending_status:
                    yield {
                        "type": "status",
                        "label": label,
                        "session_id": client_sid,
                    }

                if attempt_reply and _should_try_next_model(attempt_reply):
                    last_error = attempt_reply
                    if _is_quota_error(attempt_reply) and not is_groq:
                        skip_remaining_gemini = True
                        yield {
                            "type": "status",
                            "label": "Gemini quota hit — switching to Groq…",
                            "session_id": client_sid,
                        }
                    continue

                # Model wrote a tool plan as text instead of calling tools — try next
                if attempt_reply and _looks_like_tool_planning_leak(attempt_reply) and not pending_status:
                    last_error = "model dumped tool plan instead of calling tools"
                    yield {
                        "type": "status",
                        "label": f"{model} skipped tool calls — trying next…",
                        "session_id": client_sid,
                    }
                    continue

                if attempt_reply:
                    reply = attempt_reply
                    break
                last_error = "empty response"
                continue

            except asyncio.TimeoutError:
                last_error = (
                    f"timeout after {_MODEL_ATTEMPT_TIMEOUT_S:.0f}s on {model}"
                )
                for label in pending_status:
                    yield {
                        "type": "status",
                        "label": label,
                        "session_id": client_sid,
                    }
                yield {
                    "type": "status",
                    "label": f"Timed out on {model} — trying next…",
                    "session_id": client_sid,
                }
                if not is_groq:
                    skip_remaining_gemini = True
                continue

            except Exception as e:
                last_error = str(e)
                for label in pending_status:
                    yield {
                        "type": "status",
                        "label": label,
                        "session_id": client_sid,
                    }
                if _is_quota_error(last_error) and not is_groq:
                    skip_remaining_gemini = True
                    yield {
                        "type": "status",
                        "label": "Gemini quota hit — switching to Groq…",
                        "session_id": client_sid,
                    }
                    continue
                if _should_try_next_model(last_error):
                    continue
                reply = _friendly_error(f"An error occurred: {e}")
                break

        if not reply:
            if "tool plan instead of calling tools" in (last_error or ""):
                reply = (
                    "The model started planning tools in chat instead of running them. "
                    "Send your message once more — Trip Guide will try the next model "
                    "(or enable Ollama on your GPU box as a last fallback)."
                )
            else:
                reply = _friendly_error(last_error or _FRIENDLY_BUSY)
        elif _should_try_next_model(reply):
            reply = _friendly_error(reply)
        elif _looks_like_tool_planning_leak(reply):
            reply = (
                "I caught an incomplete tool-planning dump (board/map were not updated). "
                "Please send the same trip request again so I can retry with another model."
            )
        else:
            reply = _strip_chain_of_thought(reply)

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
        trip_context: dict[str, Any] | None = None,
    ) -> ChatResult:
        result = ChatResult(session_id=session_id or "", reply="", cards=[], activity=[])
        async for event in self.chat_events(
            message,
            session_id=session_id,
            user_id=user_id,
            trip_context=trip_context,
        ):
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
