"""Specialist leaf agents used by workflows and the router."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools import google_search

from trip_planner.config import MODEL_NAME
from trip_planner.prompts.specialists import (
    CONCERT_FINDER_INSTRUCTION,
    FOODIE_INSTRUCTION,
    FOODIE_NAVIGATE_INSTRUCTION,
    MUSEUM_FINDER_INSTRUCTION,
    RESTAURANT_FINDER_INSTRUCTION,
    SYNTHESIS_INSTRUCTION,
    TRANSPORTATION_FROM_STATE_INSTRUCTION,
    WEEKEND_GUIDE_INSTRUCTION,
)
from trip_planner.prompts.workflows import (
    CRITIC_INSTRUCTION,
    PLANNER_INSTRUCTION,
    REFINER_INSTRUCTION,
)
from trip_planner.tools.loop_control import exit_loop

# Standalone food critic (simple food-only routes)
foodie_agent = Agent(
    name="foodie_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=FOODIE_INSTRUCTION,
)

# Food finder for Sequential find-and-navigate (saves name to state)
foodie_navigate_agent = Agent(
    name="foodie_navigate_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=FOODIE_NAVIGATE_INSTRUCTION,
    output_key="destination",
)

weekend_guide_agent = Agent(
    name="weekend_guide_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=WEEKEND_GUIDE_INSTRUCTION,
)

transportation_agent = Agent(
    name="transportation_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=TRANSPORTATION_FROM_STATE_INSTRUCTION,
)

planner_agent = Agent(
    name="planner_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=PLANNER_INSTRUCTION,
    output_key="current_plan",
)

critic_agent = Agent(
    name="critic_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=CRITIC_INSTRUCTION,
    output_key="criticism",
)

refiner_agent = Agent(
    name="refiner_agent",
    model=MODEL_NAME,
    tools=[google_search, exit_loop],
    instruction=REFINER_INSTRUCTION,
    output_key="current_plan",
)

museum_finder_agent = Agent(
    name="museum_finder_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=MUSEUM_FINDER_INSTRUCTION,
    output_key="museum_result",
)

concert_finder_agent = Agent(
    name="concert_finder_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=CONCERT_FINDER_INSTRUCTION,
    output_key="concert_result",
)

restaurant_finder_agent = Agent(
    name="restaurant_finder_agent",
    model=MODEL_NAME,
    tools=[google_search],
    instruction=RESTAURANT_FINDER_INSTRUCTION,
    output_key="restaurant_result",
)

synthesis_agent = Agent(
    name="synthesis_agent",
    model=MODEL_NAME,
    instruction=SYNTHESIS_INSTRUCTION,
)
