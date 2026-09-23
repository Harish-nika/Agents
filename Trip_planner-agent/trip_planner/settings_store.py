"""Persist API keys, Ollama, and runtime mode to .env and process environment."""

from __future__ import annotations

import os
import re
from pathlib import Path

from trip_planner.config import (
    ROOT_DIR,
    VALID_RUNTIME_MODES,
    get_groq_api_key,
    get_maps_api_key,
    get_ollama_api_base,
    get_ollama_model,
    get_ollama_model_fallbacks,
    get_runtime_mode,
    model_candidates,
    ollama_configured,
    runtime_mode_label,
    sync_groq_api_key,
    sync_ollama_env,
)

ENV_PATH = ROOT_DIR / ".env"


def _mask(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:4]}…{key[-4:]}"


def settings_status() -> dict:
    """Return non-secret status of configured keys / Ollama / mode."""
    gemini_ok = False
    try:
        key = os.getenv("GOOGLE_API_KEY", "").strip()
        gemini_ok = bool(key and key != "your_api_key_here")
    except Exception:
        gemini_ok = False
    maps = get_maps_api_key()
    groq = get_groq_api_key()
    gemini_raw = os.getenv("GOOGLE_API_KEY", "").strip()
    if gemini_raw in {"", "your_api_key_here"}:
        gemini_raw = ""
    ollama_base = get_ollama_api_base()
    ollama_model = get_ollama_model()
    ollama_fallbacks = get_ollama_model_fallbacks()
    mode = get_runtime_mode()
    candidates = model_candidates()
    return {
        "google_api_key_set": gemini_ok,
        "google_maps_api_key_set": maps is not None,
        "groq_api_key_set": groq is not None,
        "ollama_configured": ollama_configured(),
        "ollama_api_base": ollama_base or None,
        "ollama_model": ollama_model or None,
        "ollama_model_fallbacks": ",".join(ollama_fallbacks) if ollama_fallbacks else None,
        "runtime_mode": mode,
        "runtime_mode_label": runtime_mode_label(mode),
        "model_candidates": candidates,
        "google_api_key_hint": _mask(gemini_raw) if gemini_ok else None,
        "google_maps_api_key_hint": _mask(maps) if maps else None,
        "groq_api_key_hint": _mask(groq) if groq else None,
        "model_order_hint": runtime_mode_label(mode),
    }


def _upsert_env_file(updates: dict[str, str]) -> None:
    path = ENV_PATH
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        example = ROOT_DIR / ".env.example"
        text = example.read_text(encoding="utf-8") if example.exists() else ""

    for key, value in updates.items():
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        line = f"{key}={value}"
        if pattern.search(text):
            text = pattern.sub(line, text)
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += line + "\n"

    if "GOOGLE_GENAI_USE_VERTEXAI=" not in text:
        text += "GOOGLE_GENAI_USE_VERTEXAI=False\n"

    path.write_text(text, encoding="utf-8")


def save_api_keys(
    google_api_key: str | None = None,
    google_maps_api_key: str | None = None,
    groq_api_key: str | None = None,
    ollama_api_base: str | None = None,
    ollama_model: str | None = None,
    ollama_model_fallbacks: str | None = None,
    runtime_mode: str | None = None,
) -> dict:
    """Save keys / Ollama / mode to .env and os.environ. Empty string clears a value."""
    updates: dict[str, str] = {}

    if google_api_key is not None:
        key = google_api_key.strip()
        updates["GOOGLE_API_KEY"] = key
        if key:
            os.environ["GOOGLE_API_KEY"] = key
        else:
            os.environ.pop("GOOGLE_API_KEY", None)

    if google_maps_api_key is not None:
        key = google_maps_api_key.strip()
        updates["GOOGLE_MAPS_API_KEY"] = key
        if key:
            os.environ["GOOGLE_MAPS_API_KEY"] = key
        else:
            os.environ.pop("GOOGLE_MAPS_API_KEY", None)

    if groq_api_key is not None:
        key = groq_api_key.strip()
        updates["GROQ_API_KEY"] = key
        updates["grok_key"] = key
        if key:
            os.environ["GROQ_API_KEY"] = key
            os.environ["grok_key"] = key
        else:
            os.environ.pop("GROQ_API_KEY", None)
            os.environ.pop("grok_key", None)

    if ollama_api_base is not None:
        base = ollama_api_base.strip().rstrip("/")
        updates["OLLAMA_API_BASE"] = base
        if base:
            os.environ["OLLAMA_API_BASE"] = base
        else:
            os.environ.pop("OLLAMA_API_BASE", None)

    if ollama_model is not None:
        model = ollama_model.strip()
        updates["OLLAMA_MODEL"] = model
        if model:
            os.environ["OLLAMA_MODEL"] = model
        else:
            os.environ.pop("OLLAMA_MODEL", None)

    if ollama_model_fallbacks is not None:
        fallbacks = ollama_model_fallbacks.strip()
        updates["OLLAMA_MODEL_FALLBACKS"] = fallbacks
        if fallbacks:
            os.environ["OLLAMA_MODEL_FALLBACKS"] = fallbacks
        else:
            os.environ.pop("OLLAMA_MODEL_FALLBACKS", None)

    if runtime_mode is not None:
        mode = runtime_mode.strip().lower()
        if mode not in VALID_RUNTIME_MODES:
            mode = "auto"
        updates["TRIP_PLANNER_RUNTIME_MODE"] = mode
        os.environ["TRIP_PLANNER_RUNTIME_MODE"] = mode

    if updates:
        updates.setdefault(
            "GOOGLE_GENAI_USE_VERTEXAI",
            os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "False"),
        )
        _upsert_env_file(updates)

    sync_groq_api_key()
    sync_ollama_env()
    return settings_status()
