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
from trip_planner.runtime.cards import begin_turn, end_turn, peek_new_cards

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
    "BADREQUESTERROR",
    "INVALID_REQUEST_ERROR",
)

_FRIENDLY_BUSY = (
    "Cloud models are busy right now. I tried the configured backups — "
    "please wait a few seconds and send your message once more "
    "(or switch to Local mode in Settings for Ollama)."
)

_MODEL_ATTEMPT_TIMEOUT_S = float(os.getenv("TRIP_PLANNER_MODEL_TIMEOUT_S", "50"))
_OLLAMA_ATTEMPT_TIMEOUT_S = float(os.getenv("TRIP_PLANNER_OLLAMA_TIMEOUT_S", "120"))


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
    if "REASONING_CONTENT" in upper:
        return (
            "That cloud model isn’t compatible with tool calling on this stack. "
            "Trip Guide will skip it — try again, or switch Runtime mode to Local in Settings."
        )
    if _is_quota_error(raw):
        return (
            "Gemini free-tier quota is used up for today. "
            "Use Groq, or switch to Local (Ollama) in Settings, then send again."
        )
    if "RATE_LIMIT" in upper or "RATE LIMIT" in upper or "TOKENS PER MINUTE" in upper:
        return (
            "Cloud rate limit hit for a moment. Wait ~30 seconds, or switch to Local mode."
        )
    if "TIMEOUT" in upper:
        return (
            "A model took too long to respond. Send once more, or try Local mode on your GPU."
        )
    if "CANCELLED" in upper or "STOPPED" in upper:
        return "Stopped."
    if _is_unavailable_model(raw):
        return (
            "That model isn’t available. I tried the next backup — send again if needed, "
            "or change Runtime mode / models in Settings."
        )
    if _is_transient_error(raw):
        return _FRIENDLY_BUSY
    cleaned = re.sub(r"^An error occurred:\s*", "", raw or "").strip()
    # Never dump huge LiteLLM JSON at users
    if len(cleaned) > 280 or cleaned.startswith("{") or "litellm" in cleaned.lower():
        return "Something went wrong with the model provider. Please try again."
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
    lower = (text or "").lower().strip()
    if not lower or len(lower) < 60:
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


def _looks_like_json_dump(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    if raw.startswith("```"):
        body = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        body = re.sub(r"\s*```$", "", body).strip()
        raw = body
    if not (raw.startswith("{") and ("}" in raw)):
        return False
    # Common tool-echo shapes even when truncated / almost-JSON
    if '"status"' in raw and (
        '"type": "trip_board"' in raw
        or '"route_stops"' in raw
        or '"days"' in raw
        or '"message":' in raw
    ):
        return True
    try:
        data = json.loads(raw)
    except Exception:
        return '"status": "success"' in raw and raw.count('"') >= 6
    if not isinstance(data, dict):
        return False
    keys = set(data.keys())
    leak_hints = {
        "status",
        "type",
        "route_stops",
        "stops",
        "days",
        "origin",
        "start_date",
        "end_date",
        "message",
    }
    return len(keys & leak_hints) >= 2


def _format_trip_context(ctx: dict[str, Any] | None) -> str:
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
    raw = (text or "").strip()
    if not raw:
        return raw
    lower = raw.lower()
    looks_like_cot = any(m in lower for m in _COT_MARKERS) or (
        lower.startswith("the user") and "we need" in lower
    )
    if not looks_like_cot:
        return raw

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
        self._cancel_flags: dict[str, asyncio.Event] = {}

    def request_cancel(self, client_session_id: str) -> None:
        flag = self._cancel_flags.get(client_session_id)
        if flag:
            flag.set()

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
        """Yield status/card/done events for streaming UI."""
        require_api_key()
        client_sid = session_id or str(uuid.uuid4())
        sid = await self._ensure_session(client_sid, user_id)
        cancel = asyncio.Event()
        self._cancel_flags[client_sid] = cancel

        begin_turn()
        reply = ""
        activity: list[str] = []
        streamed_card_ids: set[int] = set()
        last_error = ""
        models = model_candidates()
        skip_remaining_gemini = False
        agent_message = f"{_format_trip_context(trip_context)}{message}"
        cards_seen = 0

        yield {"type": "status", "label": "Thinking…", "session_id": client_sid}

        try:
            if not models:
                reply = (
                    "No models available for the current Runtime mode. "
                    "Check Settings (Local needs Ollama; Cloud needs Gemini/Groq keys)."
                )
            for index, model in enumerate(models):
                if cancel.is_set():
                    reply = "Stopped."
                    break

                mid = str(model)
                is_groq = mid.startswith("groq/")
                is_ollama = mid.startswith("ollama/")
                is_local_or_groq = is_groq or is_ollama
                if skip_remaining_gemini and not is_local_or_groq:
                    continue

                if index > 0 or skip_remaining_gemini:
                    sid = await self._ensure_session(str(uuid.uuid4()), user_id)
                    if is_groq:
                        label = f"Falling back to Groq ({model})…"
                    elif is_ollama:
                        label = f"Falling back to Ollama ({model})…"
                    else:
                        label = f"Model busy — trying {model}…"
                    yield {
                        "type": "status",
                        "label": label,
                        "session_id": client_sid,
                    }
                    await asyncio.sleep(0.05)

                runner = self._runner_for(model)
                attempt_timeout = (
                    _OLLAMA_ATTEMPT_TIMEOUT_S if is_ollama else _MODEL_ATTEMPT_TIMEOUT_S
                )
                yield {
                    "type": "status",
                    "label": f"Running {model}…",
                    "session_id": client_sid,
                    "model": mid,
                }

                event_q: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

                async def _run_once() -> str:
                    text_out = ""
                    nonlocal cards_seen
                    async for event in runner.run_async(
                        user_id=user_id,
                        session_id=sid,
                        new_message=Content(
                            parts=[Part(text=agent_message)], role="user"
                        ),
                    ):
                        if cancel.is_set():
                            raise asyncio.CancelledError()
                        for call in event.get_function_calls() or []:
                            name = getattr(call, "name", None) or ""
                            label = TOOL_STATUS_LABELS.get(name)
                            if not label:
                                # Ignore hallucinated tool names in status UI
                                if name not in TOOL_STATUS_LABELS:
                                    continue
                            if label not in activity:
                                activity.append(label)
                            await event_q.put(("status", label))
                        new_cards, cards_seen = peek_new_cards(cards_seen)
                        for card in new_cards:
                            await event_q.put(("card", card))
                        if (
                            event.is_final_response()
                            and event.content
                            and event.content.parts
                        ):
                            text = event.content.parts[0].text
                            if text:
                                text_out = text
                    return text_out

                task = asyncio.create_task(_run_once())
                attempt_reply = ""
                deadline = asyncio.get_event_loop().time() + attempt_timeout
                try:
                    while not task.done():
                        if cancel.is_set():
                            task.cancel()
                            try:
                                await task
                            except (asyncio.CancelledError, Exception):
                                pass
                            reply = "Stopped."
                            break
                        if asyncio.get_event_loop().time() > deadline:
                            raise asyncio.TimeoutError()
                        try:
                            kind, payload = await asyncio.wait_for(
                                event_q.get(), timeout=0.25
                            )
                        except asyncio.TimeoutError:
                            continue
                        if kind == "status":
                            yield {
                                "type": "status",
                                "label": payload,
                                "session_id": client_sid,
                            }
                        elif kind == "card":
                            cid = id(payload)
                            if cid not in streamed_card_ids:
                                streamed_card_ids.add(cid)
                                yield {
                                    "type": "card",
                                    "card": payload,
                                    "session_id": client_sid,
                                }
                    if reply == "Stopped.":
                        break

                    attempt_reply = await task
                    # Drain remaining queue events
                    while not event_q.empty():
                        kind, payload = event_q.get_nowait()
                        if kind == "status":
                            yield {
                                "type": "status",
                                "label": payload,
                                "session_id": client_sid,
                            }
                        elif kind == "card":
                            cid = id(payload)
                            if cid not in streamed_card_ids:
                                streamed_card_ids.add(cid)
                                yield {
                                    "type": "card",
                                    "card": payload,
                                    "session_id": client_sid,
                                }

                    if attempt_reply and _should_try_next_model(attempt_reply):
                        last_error = attempt_reply
                        if _is_quota_error(attempt_reply) and not is_local_or_groq:
                            skip_remaining_gemini = True
                            yield {
                                "type": "status",
                                "label": "Gemini quota hit — switching…",
                                "session_id": client_sid,
                            }
                        continue

                    if (
                        attempt_reply
                        and _looks_like_tool_planning_leak(attempt_reply)
                        and not activity
                    ):
                        last_error = "model dumped tool plan instead of calling tools"
                        yield {
                            "type": "status",
                            "label": f"{model} skipped tool calls — trying next…",
                            "session_id": client_sid,
                        }
                        continue

                    if attempt_reply and _looks_like_json_dump(attempt_reply):
                        # Prefer extracting nested prose over re-running tools
                        extracted = ""
                        try:
                            raw = attempt_reply.strip()
                            if raw.startswith("```"):
                                raw = re.sub(
                                    r"^```(?:json)?\s*", "", raw, flags=re.I
                                )
                                raw = re.sub(r"\s*```$", "", raw).strip()
                            data = json.loads(raw)
                            if isinstance(data, dict):
                                extracted = str(data.get("message") or "").strip()
                        except Exception:
                            extracted = ""
                        if extracted and not extracted.startswith("{"):
                            extracted = re.split(
                                r"\sDo NOT paste|\sSummarize this briefly",
                                extracted,
                                maxsplit=1,
                            )[0].strip()
                            reply = extracted
                            break
                        if activity:
                            reply = (
                                "Trip panels were updated. Ask me for a short summary "
                                "of weather and places."
                            )
                            break
                        last_error = "model echoed tool JSON"
                        yield {
                            "type": "status",
                            "label": f"{model} echoed JSON — trying next…",
                            "session_id": client_sid,
                        }
                        continue

                    if attempt_reply:
                        reply = attempt_reply
                        break
                    last_error = "empty response"
                    continue

                except asyncio.TimeoutError:
                    last_error = f"timeout after {attempt_timeout:.0f}s on {model}"
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except Exception:
                            pass
                    yield {
                        "type": "status",
                        "label": f"Timed out on {model} — trying next…",
                        "session_id": client_sid,
                    }
                    if not is_local_or_groq:
                        skip_remaining_gemini = True
                    continue

                except asyncio.CancelledError:
                    reply = "Stopped."
                    break

                except Exception as e:
                    last_error = str(e)
                    if _is_quota_error(last_error) and not is_local_or_groq:
                        skip_remaining_gemini = True
                        yield {
                            "type": "status",
                            "label": "Gemini quota hit — switching…",
                            "session_id": client_sid,
                        }
                        continue
                    if _should_try_next_model(last_error):
                        yield {
                            "type": "status",
                            "label": f"{model} failed — trying next…",
                            "session_id": client_sid,
                        }
                        continue
                    reply = _friendly_error(f"An error occurred: {e}")
                    break

            if not reply:
                if "tool plan instead of calling tools" in (last_error or ""):
                    reply = (
                        "The model planned tools in chat instead of running them. "
                        "Send again, or switch Runtime mode to Local / Cloud in Settings."
                    )
                elif "echoed tool JSON" in (last_error or ""):
                    reply = (
                        "I updated the side panels (board / weather / places). "
                        "Ask a follow-up like “summarize the weather and top places” "
                        "for a short written answer."
                    )
                else:
                    reply = _friendly_error(last_error or _FRIENDLY_BUSY)
            elif _looks_like_json_dump(reply):
                # Prefer extracting a nested message field if present
                extracted = ""
                try:
                    raw = reply.strip()
                    if raw.startswith("```"):
                        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
                        raw = re.sub(r"\s*```$", "", raw).strip()
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        extracted = str(data.get("message") or "").strip()
                except Exception:
                    extracted = ""
                if extracted and not extracted.strip().startswith("{"):
                    # Strip meta instructions from tool prose
                    extracted = re.split(
                        r"\sDo NOT paste|\sSummarize this briefly",
                        extracted,
                        maxsplit=1,
                    )[0].strip()
                    reply = extracted or (
                        "Trip panels were updated. Ask me to summarize weather and places."
                    )
                else:
                    reply = (
                        "Trip panels were updated. Ask me to continue with a short summary "
                        "of weather and places."
                    )
            elif _should_try_next_model(reply):
                reply = _friendly_error(reply)
            elif _looks_like_tool_planning_leak(reply):
                reply = (
                    "I caught an incomplete tool-planning dump. "
                    "Please send the same trip request again."
                )
            else:
                reply = _strip_chain_of_thought(reply)

            # Typewriter-friendly: stream reply in chunks
            if reply and reply != "Stopped." and len(reply) > 40:
                chunk_size = 24
                for i in range(0, len(reply), chunk_size):
                    if cancel.is_set():
                        break
                    yield {
                        "type": "token",
                        "text": reply[i : i + chunk_size],
                        "session_id": client_sid,
                    }
                    await asyncio.sleep(0.012)

            cards = end_turn()
            yield {
                "type": "done",
                "session_id": client_sid,
                "reply": reply,
                "cards": cards,
                "activity": activity,
            }
        except Exception as e:
            cards = end_turn()
            yield {
                "type": "done",
                "session_id": client_sid,
                "reply": _friendly_error(f"Trip turn failed: {e}"),
                "cards": cards,
                "activity": activity,
            }
        finally:
            self._cancel_flags.pop(client_sid, None)

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


chat_service = ChatService()
