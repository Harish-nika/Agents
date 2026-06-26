import jwt

from app.api.auth import JWT_ALGORITHM, JWT_SECRET
from app.services.user_settings_service import user_settings_service


def username_from_request(request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub") or None
    except jwt.PyJWTError:
        return None


def resolve_groq_api_key(request) -> str | None:
    if request.headers.get("x-groq-prefer", "").lower() == "ollama":
        return None
    header_key = request.headers.get("x-groq-api-key", "").strip()
    if header_key:
        return header_key
    username = username_from_request(request)
    if username:
        return user_settings_service.get_groq_key(username)
    return None
