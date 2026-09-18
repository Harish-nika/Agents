"""Parallel multi-research then synthesis workflow."""

from __future__ import annotations

from google.adk.agents import ParallelAgent, SequentialAgent

from trip_planner.agents.specialists import (
    concert_finder_agent,
    museum_finder_agent,
    restaurant_finder_agent,
    synthesis_agent,
)

parallel_research_agent = ParallelAgent(
    name="parallel_research_agent",
    sub_agents=[museum_finder_agent, concert_finder_agent, restaurant_finder_agent],
)

parallel_planner_agent = SequentialAgent(
    name="parallel_planner_agent",
    sub_agents=[parallel_research_agent, synthesis_agent],
    description="A workflow that finds multiple things in parallel and then summarizes the results.",
)
