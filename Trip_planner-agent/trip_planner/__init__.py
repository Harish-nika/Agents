"""Trip Planner ADK package — multi-agent travel assistant."""

__all__ = ["router_agent", "worker_agents", "trip_concierge"]


def __getattr__(name: str):
    if name in {"router_agent", "worker_agents"}:
        from trip_planner.agents.router import router_agent, worker_agents

        return {"router_agent": router_agent, "worker_agents": worker_agents}[name]
    if name == "trip_concierge":
        from trip_planner.agents.trip_concierge import trip_concierge

        return trip_concierge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
