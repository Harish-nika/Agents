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

# Groq tool-capable chat models (ADK function calling). Compound systems do NOT
# support tool calling — they are used via tools/compound_research.py (unlimited TPD).
# Prefer widely available Llama models; Qwen/gpt-oss may not be enabled on every key.
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile")
_GROQ_FALLBACK_RAW = os.getenv(
    "GROQ_MODEL_FALLBACKS",
    "groq/llama-3.1-8b-instant,groq/openai/gpt-oss-20b",
)
GROQ_MODEL_FALLBACKS = [m.strip() for m in _GROQ_FALLBACK_RAW.split(",") if m.strip()]

# Optional local GPU via Ollama (e.g. http://192.168.0.183:11434)
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "").strip().rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()  # e.g. ollama/llama3.1:70b
_OLLAMA_FALLBACK_RAW = os.getenv("OLLAMA_MODEL_FALLBACKS", "")
OLLAMA_MODEL_FALLBACKS = [m.strip() for m in _OLLAMA_FALLBACK_RAW.split(",") if m.strip()]

DEFAULT_USER_ID = os.getenv("TRIP_PLANNER_USER_ID", "adk_adventurer_001")
APP_NAME = "trip_planner"
HOST = os.getenv("TRIP_PLANNER_HOST", "0.0.0.0")
PORT = int(os.getenv("TRIP_PLANNER_PORT", "8080"))

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "False")
if OLLAMA_API_BASE:
    # LiteLLM / OpenAI-compatible clients read this for Ollama
    os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_API_BASE)


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


def _normalize_groq_id(name: str) -> str:
    return name if name.startswith("groq/") else f"groq/{name}"


def _litellm_model_id(mid: str) -> str:
    """Map our model ids to LiteLLM ids.

    Groq model ids that already contain a slash (e.g. ``openai/gpt-oss-20b``,
    ``qwen/qwen3.8-27b``, ``groq/compound``) need an extra ``groq/`` provider
    prefix so LiteLLM sends the full id to the Groq API.
    """
    if mid.startswith("groq/") and mid.count("/") >= 2:
        # Already groq/<org>/<name> — LiteLLM provider + model path is correct
        return mid
    if mid in {"groq/compound", "groq/compound-mini"}:
        return f"groq/{mid}"
    return mid


def _normalize_ollama_id(name: str) -> str:
    return name if name.startswith("ollama/") else f"ollama/{name}"


def model_candidates() -> list[str]:
    """Primary Gemini → Gemini fallbacks → Groq → optional Ollama GPU last.

    Set TRIP_PLANNER_SKIP_GEMINI=1 to use Groq only (useful when Gemini free
    tier daily quota is exhausted).
    """
    seen: set[str] = set()
    out: list[str] = []
    skip_gemini = os.getenv("TRIP_PLANNER_SKIP_GEMINI", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    def _add(name: str) -> None:
        if not name or name in seen or name in _RETIRED_MODELS:
            return
        # Compound cannot be an ADK agent model (no tool calling)
        if name in {"groq/compound", "groq/compound-mini"}:
            return
        seen.add(name)
        out.append(name)

    if not skip_gemini:
        _add(MODEL_NAME)
        for name in MODEL_FALLBACKS:
            _add(name)
    if get_groq_api_key():
        for name in [GROQ_MODEL, *GROQ_MODEL_FALLBACKS]:
            if name:
                _add(_normalize_groq_id(name))
    if OLLAMA_API_BASE and (OLLAMA_MODEL or OLLAMA_MODEL_FALLBACKS):
        for name in [OLLAMA_MODEL, *OLLAMA_MODEL_FALLBACKS]:
            if name:
                _add(_normalize_ollama_id(name))
    if not out and not skip_gemini:
        out = ["gemini-2.0-flash"]
    return out


def tool_capable_model(preferred: str | None = None) -> str:
    """Model for specialists — never Compound (no ADK tool calling)."""
    mid = preferred or MODEL_NAME
    if mid.startswith("groq/compound"):
        for name in [MODEL_NAME, *MODEL_FALLBACKS]:
            if name and name not in _RETIRED_MODELS:
                return name
        if OLLAMA_MODEL:
            return _normalize_ollama_id(OLLAMA_MODEL)
        return "gemini-2.0-flash"
    return mid


def resolve_model(model_id: str | None = None):
    """Return a model id string or LiteLlm wrapper for Groq/OpenAI-compatible providers."""
    mid = model_id or MODEL_NAME
    if mid.startswith("groq/") or mid.startswith("openai/") or mid.startswith("ollama/"):
        sync_groq_api_key()
        from google.adk.models.lite_llm import LiteLlm

        kwargs: dict = {"model": _litellm_model_id(mid)}
        if mid.startswith("ollama/") and OLLAMA_API_BASE:
            kwargs["api_base"] = OLLAMA_API_BASE
        return LiteLlm(**kwargs)
    return mid


def require_api_key() -> str:
    """Return GOOGLE_API_KEY or raise a clear error.

    Groq-only or Ollama-only mode is allowed when those backends are configured.
    """
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if key and key != "your_api_key_here":
        os.environ["GOOGLE_API_KEY"] = key
        return key
    if get_groq_api_key():
        return "groq-only"
    if OLLAMA_API_BASE and (OLLAMA_MODEL or OLLAMA_MODEL_FALLBACKS):
        return "ollama-only"
    raise RuntimeError(
        "No LLM key set. Add GOOGLE_API_KEY and/or grok_key (Groq) in Settings / .env, "
        "or set OLLAMA_API_BASE + OLLAMA_MODEL for your GPU box."
    )


def get_maps_api_key() -> str | None:
    """Return GOOGLE_MAPS_API_KEY if configured."""
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key or key == "your_maps_api_key_here":
        return None
    return key


# Sync on import so LiteLLM sees the key even if stored as grok_key
sync_groq_api_key()
