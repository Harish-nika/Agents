from typing import Any

from app.config import GROQ_FAST_MODEL, GROQ_LLM_MODEL
from app.services.groq_client import groq_client
from app.services.llm_context import get_groq_api_key
from app.services.ollama_client import ollama_client


class LLMClient:
    """Routes chat to Groq when a personal API key is set, else Ollama."""

    def chat_json(
        self,
        system: str,
        user: str,
        retries: int = 3,
        model: str | None = None,
        use_gpu: bool = True,
        fast: bool = False,
    ) -> dict[str, Any]:
        groq_key = get_groq_api_key()
        if groq_key:
            groq_model = GROQ_FAST_MODEL if fast else (model or GROQ_LLM_MODEL)
            return groq_client.chat_json(groq_key, system, user, model=groq_model, retries=retries)
        ollama_model = ollama_client.fast_model if fast else model
        return ollama_client.chat_json(
            system, user, retries=retries, model=ollama_model, use_gpu=use_gpu and not fast
        )

    def chat_text(self, system: str, user: str, fast: bool = True) -> str:
        groq_key = get_groq_api_key()
        if groq_key:
            return groq_client.chat_text(
                groq_key, system, user, model=GROQ_FAST_MODEL if fast else GROQ_LLM_MODEL
            )
        import httpx
        from app.config import OLLAMA_BASE_URL, OLLAMA_FAST_MODEL, OLLAMA_LLM_MODEL, OLLAMA_TIMEOUT

        ollama_model = OLLAMA_FAST_MODEL if fast else OLLAMA_LLM_MODEL
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            resp = client.post(
                f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={"model": ollama_model, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()

    def using_groq(self) -> bool:
        return bool(get_groq_api_key())

    def embed(self, text: str) -> list[float]:
        return ollama_client.embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return ollama_client.embed_batch(texts)

    def health_status(self) -> dict[str, bool]:
        status = ollama_client.health_status()
        groq_key = get_groq_api_key()
        status["groq"] = groq_client.health_check(groq_key) if groq_key else False
        return status


llm_client = LLMClient()
