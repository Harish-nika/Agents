"""Groq Compound research — unlimited-TPD system (no ADK function tools)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from trip_planner.config import get_groq_api_key


def compound_research(query: str, use_mini: bool = False) -> dict[str, Any]:
    """Ask Groq Compound (built-in web search) for a short research answer.

    Compound systems do not support OpenAI-style tool calling, so they cannot
    be used as the ADK agent model. Call this tool instead for unlimited-TPD
    web research when Gemini/places search needs a boost.
    """
    key = get_groq_api_key()
    if not key:
        return {"status": "error", "error": "No Groq key configured (grok_key / GROQ_API_KEY)."}

    model = "groq/compound-mini" if use_mini else "groq/compound"
    print(f"TOOL CALLED: compound_research(model={model}, query='{query[:80]}...')")
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a travel research assistant. Answer briefly with "
                        "concrete place names, vibes, and tips. No fluff."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "temperature": 0.3,
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "TripGuide/1.0 (+https://localhost)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:400]
        return {"status": "error", "error": err or str(e), "model": model}
    except Exception as e:
        return {"status": "error", "error": str(e), "model": model}

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return {"status": "error", "error": "Empty Compound response", "raw": data}

    return {"status": "success", "model": model, "answer": text}
