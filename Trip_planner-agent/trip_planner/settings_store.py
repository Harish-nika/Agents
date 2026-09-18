"""Persist API keys to .env and process environment."""

from __future__ import annotations

import os
import re
from pathlib import Path

from trip_planner.config import (
    ROOT_DIR,
    get_groq_api_key,
    get_maps_api_key,
    sync_groq_api_key,
)

ENV_PATH = ROOT_DIR / ".env"


def _mask(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:4]}…{key[-4:]}"


def settings_status() -> dict:
    """Return non-secret status of configured keys."""
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
    return {
        "google_api_key_set": gemini_ok,
        "google_maps_api_key_set": maps is not None,
        "groq_api_key_set": groq is not None,
        "google_api_key_hint": _mask(gemini_raw) if gemini_ok else None,
        "google_maps_api_key_hint": _mask(maps) if maps else None,
        "groq_api_key_hint": _mask(groq) if groq else None,
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
) -> dict:
    """Save keys to .env and os.environ. Empty string clears a key."""
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
        updates["grok_key"] = key  # alias the user already uses
        if key:
            os.environ["GROQ_API_KEY"] = key
            os.environ["grok_key"] = key
        else:
            os.environ.pop("GROQ_API_KEY", None)
            os.environ.pop("grok_key", None)

    if updates:
        updates.setdefault(
            "GOOGLE_GENAI_USE_VERTEXAI",
            os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "False"),
        )
        _upsert_env_file(updates)

    sync_groq_api_key()
    return settings_status()
