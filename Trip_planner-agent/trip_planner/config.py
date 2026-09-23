"""Configuration for the trip planner ADK package."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MODEL_NAME = os.getenv("TRIP_PLANNER_MODEL", "gemini-2.0-flash")
# Comma-separated Gemini fallbacks (never include retired models)
_FALLBACK_RAW = os.getenv(
    "TRIP_PLANNER_MODEL_FALLBACKS",
    "gemini-flash-latest,gemini-2.0-flash",
)
MODEL_FALLBACKS = [m.strip() for m in _FALLBACK_RAW.split(",") if m.strip()]
# Models Google has retired for new API keys — always skip
_RETIRED_MODELS = {
    "gemini-3.6-flash",
    "models/gemini-3.6-flash",
    "gemini-2.5-flash",
    "models/gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
}

# Groq models that break ADK tool loops (reasoning_content / no tool calling)
_GROQ_BLOCKLIST_SUBSTRINGS = (
    "gpt-oss",
    "compound",
    "whisper",
    "prompt-guard",
    "orpheus",
)

# Default Groq = models commonly available on free/project keys (override in .env)
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/qwen/qwen3.8-27b")
_GROQ_FALLBACK_RAW = os.getenv("GROQ_MODEL_FALLBACKS", "")
GROQ_MODEL_FALLBACKS = [m.strip() for m in _GROQ_FALLBACK_RAW.split(",") if m.strip()]

DEFAULT_USER_ID = os.getenv("TRIP_PLANNER_USER_ID", "adk_adventurer_001")
APP_NAME = "trip_planner"
HOST = os.getenv("TRIP_PLANNER_HOST", "0.0.0.0")
PORT = int(os.getenv("TRIP_PLANNER_PORT", "8080"))

VALID_RUNTIME_MODES = ("auto", "local", "cloud")

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "False")


def get_runtime_mode() -> str:
    """auto | local | cloud — user-controlled via Settings / .env."""
    raw = os.getenv("TRIP_PLANNER_RUNTIME_MODE", "auto").strip().lower()
    if raw in VALID_RUNTIME_MODES:
        return raw
    # Back-compat: PREFER_OLLAMA=1 ⇒ local preference within auto
    if os.getenv("TRIP_PLANNER_PREFER_OLLAMA", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return "local"
    return "auto"


def runtime_mode_label(mode: str | None = None) -> str:
    m = mode or get_runtime_mode()
    return {
        "auto": "Auto (cloud → local)",
        "local": "Local GPU (Ollama)",
        "cloud": "Cloud (Gemini / Groq)",
    }.get(m, "Auto (cloud → local)")


def get_ollama_api_base() -> str:
    return os.getenv("OLLAMA_API_BASE", "").strip().rstrip("/")


def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "").strip()


def get_ollama_model_fallbacks() -> list[str]:
    raw = os.getenv("OLLAMA_MODEL_FALLBACKS", "")
    return [m.strip() for m in raw.split(",") if m.strip()]


def ollama_configured() -> bool:
    return bool(get_ollama_api_base() and (get_ollama_model() or get_ollama_model_fallbacks()))


def sync_ollama_env() -> None:
    """Expose OLLAMA_API_BASE to LiteLLM when configured."""
    base = get_ollama_api_base()
    if base:
        os.environ["OLLAMA_API_BASE"] = base


# Back-compat aliases (read once at import; prefer getters for live Settings updates)
OLLAMA_API_BASE = get_ollama_api_base()
OLLAMA_MODEL = get_ollama_model()
OLLAMA_MODEL_FALLBACKS = get_ollama_model_fallbacks()
sync_ollama_env()


def sync_groq_api_key() -> str | None:
    """Load Groq key from GROQ_API_KEY or grok_key alias into GROQ_API_KEY for LiteLLM."""
    key = (
        os.getenv("GROQ_API_KEY", "").strip()
        or os.getenv("grok_key", "").strip()
        or os.getenv("GROK_KEY", "").strip()
    )
    if not key or key.startswith("your_"):
        return None
    os.environ["GROQ_API_KEY"] = key
    return key


def get_groq_api_key() -> str | None:
    return sync_groq_api_key()


def gemini_configured() -> bool:
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    return bool(key and key != "your_api_key_here" and not key.startswith("your_"))


def _normalize_groq_id(name: str) -> str:
    return name if name.startswith("groq/") else f"groq/{name}"


def _litellm_model_id(mid: str) -> str:
    """Map our model ids to LiteLLM ids."""
    if mid.startswith("groq/") and mid.count("/") >= 2:
        return mid
    if mid in {"groq/compound", "groq/compound-mini"}:
        return f"groq/{mid}"
    return mid


def _normalize_ollama_id(name: str) -> str:
    return name if name.startswith("ollama/") else f"ollama/{name}"


def _is_blocked_groq(name: str) -> bool:
    lower = name.lower()
    return any(s in lower for s in _GROQ_BLOCKLIST_SUBSTRINGS)


def model_candidates() -> list[str]:
    """Build model list from runtime mode + configured keys.

    Modes:
      auto  — Gemini → Groq → Ollama (skip Gemini if TRIP_PLANNER_SKIP_GEMINI=1)
      local — Ollama only
      cloud — Gemini → Groq only
    """
    seen: set[str] = set()
    out: list[str] = []
    mode = get_runtime_mode()
    skip_gemini = os.getenv("TRIP_PLANNER_SKIP_GEMINI", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    def _add(name: str) -> None:
        if not name or name in seen or name in _RETIRED_MODELS:
            return
        if name.startswith("groq/") and _is_blocked_groq(name):
            return
        if name in {"groq/compound", "groq/compound-mini"}:
            return
        seen.add(name)
        out.append(name)

    def _add_ollama() -> None:
        if not ollama_configured():
            return
        sync_ollama_env()
        for name in [get_ollama_model(), *get_ollama_model_fallbacks()]:
            if name:
                _add(_normalize_ollama_id(name))

    def _add_groq() -> None:
        if not get_groq_api_key():
            return
        for name in [GROQ_MODEL, *GROQ_MODEL_FALLBACKS]:
            if name:
                _add(_normalize_groq_id(name))

    def _add_gemini() -> None:
        if skip_gemini or not gemini_configured():
            return
        _add(MODEL_NAME)
        for name in MODEL_FALLBACKS:
            _add(name)

    if mode == "local":
        _add_ollama()
    elif mode == "cloud":
        _add_gemini()
        _add_groq()
        if not out and not skip_gemini and gemini_configured():
            out = ["gemini-2.0-flash"]
    else:  # auto
        _add_gemini()
        _add_groq()
        _add_ollama()
        if not out and not skip_gemini and gemini_configured():
            out = ["gemini-2.0-flash"]
    return out


def tool_capable_model(preferred: str | None = None) -> str:
    """Model for specialists — never Compound (no ADK tool calling)."""
    mid = preferred or MODEL_NAME
    if mid.startswith("groq/compound") or _is_blocked_groq(mid):
        for name in [MODEL_NAME, *MODEL_FALLBACKS]:
            if name and name not in _RETIRED_MODELS:
                return name
        om = get_ollama_model()
        if om:
            return _normalize_ollama_id(om)
        return "gemini-2.0-flash"
    return mid


def resolve_model(model_id: str | None = None):
    """Return a model id string or LiteLlm wrapper for Groq/OpenAI-compatible providers."""
    mid = model_id or MODEL_NAME
    if mid.startswith("groq/") or mid.startswith("openai/") or mid.startswith("ollama/"):
        sync_groq_api_key()
        from google.adk.models.lite_llm import LiteLlm

        kwargs: dict = {"model": _litellm_model_id(mid)}
        if mid.startswith("ollama/"):
            sync_ollama_env()
            base = get_ollama_api_base()
            if base:
                kwargs["api_base"] = base
            kwargs.setdefault("api_key", "ollama")
        return LiteLlm(**kwargs)
    return mid


def require_api_key() -> str:
    """Ensure at least one backend matches the current runtime mode."""
    mode = get_runtime_mode()
    if mode == "local":
        if ollama_configured():
            return "ollama-only"
        raise RuntimeError(
            "Local mode is on but Ollama is not configured. "
            "Set OLLAMA_API_BASE + OLLAMA_MODEL in Settings, or switch to Auto/Cloud."
        )
    if mode == "cloud":
        if gemini_configured():
            key = os.getenv("GOOGLE_API_KEY", "").strip()
            os.environ["GOOGLE_API_KEY"] = key
            return key
        if get_groq_api_key():
            return "groq-only"
        raise RuntimeError(
            "Cloud mode needs a Gemini or Groq key in Settings "
            "(or switch to Local / Auto with Ollama)."
        )
    # auto
    if gemini_configured():
        key = os.getenv("GOOGLE_API_KEY", "").strip()
        os.environ["GOOGLE_API_KEY"] = key
        return key
    if get_groq_api_key():
        return "groq-only"
    if ollama_configured():
        return "ollama-only"
    raise RuntimeError(
        "No LLM configured. Add Gemini/Groq keys in Settings, "
        "or set OLLAMA_API_BASE + OLLAMA_MODEL for local GPU."
    )


def get_maps_api_key() -> str | None:
    """Return GOOGLE_MAPS_API_KEY if configured."""
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key or key == "your_maps_api_key_here":
        return None
    return key


sync_groq_api_key()
