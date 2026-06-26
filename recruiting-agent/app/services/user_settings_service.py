from datetime import datetime

from app.db.models import UserSettings, get_session


def mask_groq_key(key: str) -> str:
    key = key.strip()
    if len(key) <= 12:
        return "••••••••"
    return f"{key[:7]}...{key[-4:]}"


class UserSettingsService:
    def get_groq_key(self, username: str) -> str | None:
        session = get_session()
        try:
            row = session.query(UserSettings).filter(UserSettings.username == username).first()
            if row and row.groq_api_key.strip():
                return row.groq_api_key.strip()
            return None
        finally:
            session.close()

    def get_groq_status(self, username: str) -> dict:
        session = get_session()
        try:
            row = session.query(UserSettings).filter(UserSettings.username == username).first()
            if row and row.groq_api_key.strip():
                return {
                    "has_saved_key": True,
                    "key_mask": mask_groq_key(row.groq_api_key),
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
            return {"has_saved_key": False, "key_mask": "", "updated_at": None}
        finally:
            session.close()

    def save_groq_key(self, username: str, api_key: str) -> dict:
        key = api_key.strip()
        if not key:
            raise ValueError("API key cannot be empty")
        session = get_session()
        try:
            row = session.query(UserSettings).filter(UserSettings.username == username).first()
            if not row:
                row = UserSettings(username=username, groq_api_key=key)
                session.add(row)
            else:
                row.groq_api_key = key
                row.updated_at = datetime.utcnow()
            session.commit()
            return self.get_groq_status(username)
        finally:
            session.close()

    def delete_groq_key(self, username: str) -> None:
        session = get_session()
        try:
            row = session.query(UserSettings).filter(UserSettings.username == username).first()
            if row:
                row.groq_api_key = ""
                row.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()


user_settings_service = UserSettingsService()
