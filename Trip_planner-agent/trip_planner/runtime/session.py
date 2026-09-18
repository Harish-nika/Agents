"""Session service helpers."""

from __future__ import annotations

from google.adk.sessions import InMemorySessionService, Session

from trip_planner.config import DEFAULT_USER_ID


def create_session_service() -> InMemorySessionService:
    """Create an in-memory session service for CLI / demos."""
    return InMemorySessionService()


async def new_session(
    session_service: InMemorySessionService,
    app_name: str,
    user_id: str = DEFAULT_USER_ID,
) -> Session:
    """Create a new session for an agent run."""
    return await session_service.create_session(app_name=app_name, user_id=user_id)
