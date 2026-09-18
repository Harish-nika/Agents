"""Ultimate router agent and worker registry."""

from __future__ import annotations

from google.adk.agents import Agent, BaseAgent

from trip_planner.agents.concierge_team import trip_data_concierge
from trip_planner.agents.day_trip import day_trip_agent
from trip_planner.agents.multi_day import multi_day_trip_agent
from trip_planner.agents.specialists import foodie_agent, weekend_guide_agent
from trip_planner.agents.weather_planner import weather_aware_planner
from trip_planner.config import MODEL_NAME
from trip_planner.prompts.router import ROUTER_INSTRUCTION
from trip_planner.workflows.find_and_navigate import find_and_navigate_agent
from trip_planner.workflows.iterative_planner import iterative_planner_agent
from trip_planner.workflows.parallel_planner import parallel_planner_agent

router_agent = Agent(
    name="router_agent",
    model=MODEL_NAME,
    instruction=ROUTER_INSTRUCTION,
)

# weekend_guide_agent is defined but omitted from the default registry
# (matches the final Lesson 2 notebook). Import it if you need events routing.
worker_agents: dict[str, BaseAgent] = {
    "day_trip_agent": day_trip_agent,
    "foodie_agent": foodie_agent,
    "find_and_navigate_agent": find_and_navigate_agent,
    "iterative_planner_agent": iterative_planner_agent,
    "parallel_planner_agent": parallel_planner_agent,
    "weather_aware_planner": weather_aware_planner,
    "trip_data_concierge": trip_data_concierge,
    "multi_day_trip_agent": multi_day_trip_agent,
}

__all__ = [
    "router_agent",
    "worker_agents",
    "weekend_guide_agent",
]
