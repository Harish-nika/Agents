import json
import time
from typing import Any

import httpx

from app.config import GROQ_FAST_MODEL, GROQ_LLM_MODEL, GROQ_TIMEOUT


class GroqError(Exception):
    pass


class GroqClient:
    base_url = "https://api.groq.com/openai/v1"

    def health_check(self, api_key: str) -> bool:
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def chat_json(
        self,
        api_key: str,
        system: str,
        user: str,
        model: str | None = None,
        retries: int = 3,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        payload: dict[str, Any] = {
            "model": model or GROQ_LLM_MODEL,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                data = self._post(api_key, "/chat/completions", payload)
                content = data["choices"][0]["message"]["content"]
                return self._parse_json(content)
            except (GroqError, json.JSONDecodeError, KeyError, IndexError) as exc:
                last_error = exc
                if attempt < retries - 1:
                    delay = 2 ** (attempt + 1) if "429" in str(exc) else 2**attempt
                    time.sleep(delay)
                    messages.append(
                        {
                            "role": "user",
                            "content": "Return valid JSON only. Fix any formatting issues.",
                        }
                    )
                    payload["messages"] = messages
        raise GroqError(f"Failed to get valid JSON from Groq: {last_error}")

    def chat_text(
        self,
        api_key: str,
        system: str,
        user: str,
        model: str | None = None,
        retries: int = 4,
    ) -> str:
        payload = {
            "model": model or GROQ_FAST_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                data = self._post(api_key, "/chat/completions", payload)
                return str(data["choices"][0]["message"]["content"]).strip()
            except GroqError as exc:
                last_error = exc
                if "429" in str(exc) and attempt < retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise
        raise GroqError(f"Groq request failed: {last_error}")

    def _post(self, api_key: str, path: str, payload: dict[str, Any], retries: int = 4) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=GROQ_TIMEOUT) as client:
                    response = client.post(
                        f"{self.base_url}{path}",
                        json=payload,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status == 429 and attempt < retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise GroqError(f"Groq request failed: {exc}") from exc
        raise GroqError(f"Groq request failed: {last_error}")

    def _parse_json(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(content)


groq_client = GroqClient()
