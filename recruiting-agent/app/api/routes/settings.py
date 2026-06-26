import jwt
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import JWT_ALGORITHM, JWT_SECRET, get_current_user
from app.api.schemas import GroqKeySave, GroqSettingsPublic
from app.services.user_settings_service import user_settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/groq", response_model=GroqSettingsPublic)
def get_groq_settings(user: str = Depends(get_current_user)):
    return GroqSettingsPublic(**user_settings_service.get_groq_status(user))


@router.put("/groq", response_model=GroqSettingsPublic)
def save_groq_settings(body: GroqKeySave, user: str = Depends(get_current_user)):
    try:
        return GroqSettingsPublic(**user_settings_service.save_groq_key(user, body.api_key))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/groq")
def delete_groq_settings(user: str = Depends(get_current_user)):
    user_settings_service.delete_groq_key(user)
    return {"ok": True}
