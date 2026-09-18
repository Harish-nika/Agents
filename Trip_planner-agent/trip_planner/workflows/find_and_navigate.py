"""Sequential find-restaurant-then-navigate workflow."""

from __future__ import annotations

from google.adk.agents import SequentialAgent

from trip_planner.agents.specialists import foodie_navigate_agent, transportation_agent

find_and_navigate_agent = SequentialAgent(
    name="find_and_navigate_agent",
    sub_agents=[foodie_navigate_agent, transportation_agent],
    description="A workflow that first finds a location and then provides directions to it.",
)
