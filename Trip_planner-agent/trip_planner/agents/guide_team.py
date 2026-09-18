"""Specialist sub-agents used as AgentTools by Trip Guide."""

from __future__ import annotations

from google.adk.agents import Agent

from trip_planner.config import MODEL_NAME, resolve_model
from trip_planner.prompts.guide_specialists import (
    PLACES_SPECIALIST_INSTRUCTION,
    STAYS_SPECIALIST_INSTRUCTION,
    WEATHER_SPECIALIST_INSTRUCTION,
)
from trip_planner.tools.compound_research import compound_research
from trip_planner.tools.specialist_tools import (
    search_lodging,
    suggest_food,
    suggest_places,
)
from trip_planner.tools.weather import get_live_weather_forecast, get_weather_for_dates
from trip_planner.tools.web_search import web_search


def build_weather_specialist(model: str | None = None) -> Agent:
    return Agent(
        name="weather_specialist",
        model=resolve_model(model or MODEL_NAME),
        description="Climate and forecast for trip stops and dates.",
        instruction=WEATHER_SPECIALIST_INSTRUCTION,
        tools=[get_weather_for_dates, get_live_weather_forecast],
    )


def build_places_specialist(model: str | None = None) -> Agent:
    return Agent(
        name="places_specialist",
        model=resolve_model(model or MODEL_NAME),
        description="Best-rated attractions and notable places.",
        instruction=PLACES_SPECIALIST_INSTRUCTION,
        tools=[suggest_places, compound_research, web_search],
    )


def build_stays_specialist(model: str | None = None) -> Agent:
    return Agent(
        name="stays_specialist",
        model=resolve_model(model or MODEL_NAME),
        description="Food and lodging suggestions when requested.",
        instruction=STAYS_SPECIALIST_INSTRUCTION,
        tools=[suggest_food, search_lodging, compound_research],
    )
