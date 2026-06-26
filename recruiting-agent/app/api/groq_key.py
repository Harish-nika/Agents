from fastapi import Header, Request

from app.services.user_settings_service import user_settings_service


def get_groq_key_header(x_groq_api_key: str | None = Header(None, alias="X-Groq-API-Key")) -> str | None:
    if not x_groq_api_key:
        return None
    key = x_groq_api_key.strip()
    return key or None


def effective_groq_key(
    request: Request,
    header_key: str | None,
    username: str,
) -> str | None:
    prefer = request.headers.get("x-groq-prefer", "").lower()
    if prefer == "ollama":
        return None
    if header_key:
        return header_key
    if prefer == "saved" or not prefer:
        return user_settings_service.get_groq_key(username)
    return user_settings_service.get_groq_key(username)
