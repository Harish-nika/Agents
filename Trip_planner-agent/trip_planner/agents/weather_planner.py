"""Weather-aware trip planner agent."""

from __future__ import annotations

from google.adk.agents import Agent

from trip_planner.config import MODEL_NAME
from trip_planner.prompts.day_trip import (
    WEATHER_PLANNER_DESCRIPTION,
    WEATHER_PLANNER_INSTRUCTION,
)
from trip_planner.tools.weather import get_live_weather_forecast

weather_aware_planner = Agent(
    name="weather_aware_planner",
    model=MODEL_NAME,
    description=WEATHER_PLANNER_DESCRIPTION,
    instruction=WEATHER_PLANNER_INSTRUCTION,
    tools=[get_live_weather_forecast],
)
