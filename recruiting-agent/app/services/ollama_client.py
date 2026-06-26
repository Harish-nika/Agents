import json
import time
from typing import Any

import httpx

from app.config import (
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_FAST_MODEL,
    OLLAMA_GPU_BASE_URL,
    OLLAMA_LLM_MODEL,
    OLLAMA_TIMEOUT,
)


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self) -> None:
        self.cpu_url = OLLAMA_BASE_URL.rstrip("/")
        self.gpu_url = OLLAMA_GPU_BASE_URL.rstrip("/")
        self.llm_model = OLLAMA_LLM_MODEL
        self.fast_model = OLLAMA_FAST_MODEL
        self.embed_model = OLLAMA_EMBED_MODEL

    def health_check(self, use_gpu: bool = False) -> bool:
        url = self.gpu_url if use_gpu else self.cpu_url
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(f"{url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def health_status(self) -> dict[str, bool]:
        return {
            "ollama_cpu": self.health_check(use_gpu=False),
            "ollama_gpu": self.health_check(use_gpu=True),
            "ollama": self.health_check(use_gpu=False) or self.health_check(use_gpu=True),
        }

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.embed_model, "prompt": text}
        data = self._post("/api/embeddings", payload, base_url=self.cpu_url)
        embedding = data.get("embedding")
        if not embedding:
            raise OllamaError("No embedding returned from Ollama")
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    def chat_json(
        self,
        system: str,
        user: str,
        retries: int = 3,
        model: str | None = None,
        use_gpu: bool = True,
    ) -> dict[str, Any]:
        base_url = self.gpu_url if use_gpu else self.cpu_url
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        payload = {
            "model": model or self.llm_model,
            "messages": messages,
            "stream": False,
            "format": "json",
        }
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                data = self._post("/api/chat", payload, base_url=base_url)
                content = data.get("message", {}).get("content", "")
                return self._parse_json(content)
            except (OllamaError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                    payload["messages"].append(
                        {
                            "role": "user",
                            "content": "Return valid JSON only. Fix any formatting issues.",
                        }
                    )
        raise OllamaError(f"Failed to get valid JSON from Ollama: {last_error}")

    def _post(self, path: str, payload: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
        url = (base_url or self.cpu_url).rstrip("/")
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
                response = client.post(f"{url}{path}", json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc

    def _parse_json(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(content)


ollama_client = OllamaClient()
