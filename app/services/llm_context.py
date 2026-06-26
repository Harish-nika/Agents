from contextvars import ContextVar

_groq_api_key: ContextVar[str | None] = ContextVar("groq_api_key", default=None)


def get_groq_api_key() -> str | None:
    key = _groq_api_key.get()
    return key.strip() if key else None


def set_groq_api_key(key: str | None):
    return _groq_api_key.set(key.strip() if key else None)


def reset_groq_api_key(token) -> None:
    _groq_api_key.reset(token)
