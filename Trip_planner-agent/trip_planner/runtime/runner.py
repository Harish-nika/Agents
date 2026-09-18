"""ADK Runner helpers (no IPython / Colab dependencies)."""

from __future__ import annotations

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai.types import Content, Part

from trip_planner.config import DEFAULT_USER_ID


async def run_agent_query(
    agent: BaseAgent,
    query: str,
    session: Session,
    session_service: InMemorySessionService,
    user_id: str = DEFAULT_USER_ID,
    *,
    verbose: bool = False,
    is_router: bool = False,
) -> str:
    """Run a single query against an agent and return the final response text."""
    print(f"\nRunning query for agent: '{agent.name}' in session: '{session.id}'...")

    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name=agent.name,
    )

    final_response = ""
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=Content(parts=[Part(text=query)], role="user"),
        ):
            if verbose and not is_router:
                print(f"EVENT: {event}")
            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text or ""
    except Exception as e:
        final_response = f"An error occurred: {e}"

    if not is_router:
        print("\n" + "-" * 50)
        print("Final Response:")
        print(final_response)
        print("-" * 50 + "\n")

    return final_response
