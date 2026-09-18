"""CLI entry: route a user query to the best specialist or workflow."""

from __future__ import annotations

import argparse
import asyncio
import sys

from trip_planner.agents.router import router_agent, worker_agents
from trip_planner.config import DEFAULT_USER_ID, require_api_key
from trip_planner.runtime.runner import run_agent_query
from trip_planner.runtime.session import create_session_service, new_session


def _normalize_route(raw: str) -> str:
    return raw.strip().strip("'\"`").split()[0] if raw.strip() else ""


async def run_routed_query(
    query: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    verbose: bool = False,
) -> str:
    """Classify with the router, then run the chosen worker agent."""
    require_api_key()
    session_service = create_session_service()

    print(f"\n{'=' * 60}")
    print(f"Processing query: '{query}'")
    print("=" * 60)

    router_session = await new_session(session_service, router_agent.name, user_id)
    print("Asking the router agent to make a decision...")
    chosen_route = await run_agent_query(
        router_agent,
        query,
        router_session,
        session_service,
        user_id,
        verbose=verbose,
        is_router=True,
    )
    chosen_route = _normalize_route(chosen_route)
    print(f"Router selected route: '{chosen_route}'")

    if chosen_route not in worker_agents:
        message = f"Error: Router chose an unknown route: '{chosen_route}'"
        print(message)
        print(f"Available routes: {', '.join(sorted(worker_agents))}")
        return message

    worker_agent = worker_agents[chosen_route]
    print(f"--- Handing off to {worker_agent.name} ---")
    worker_session = await new_session(session_service, worker_agent.name, user_id)
    response = await run_agent_query(
        worker_agent,
        query,
        worker_session,
        session_service,
        user_id,
        verbose=verbose,
    )
    print(f"--- {worker_agent.name} Complete ---")
    return response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Trip Planner ADK agent — route a query to the best specialist."
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Natural-language trip planning request",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print intermediate ADK events",
    )
    parser.add_argument(
        "--list-routes",
        action="store_true",
        help="List registered worker agent names and exit",
    )
    args = parser.parse_args(argv)

    if args.list_routes:
        for name in sorted(worker_agents):
            print(name)
        return 0

    if not args.query:
        parser.error("query is required (or use --list-routes)")

    try:
        asyncio.run(run_routed_query(args.query, verbose=args.verbose))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
