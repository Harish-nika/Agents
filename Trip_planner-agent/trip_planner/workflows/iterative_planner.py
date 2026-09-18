"""Iterative plan → critique → refine LoopAgent workflow."""

from __future__ import annotations

from google.adk.agents import LoopAgent, SequentialAgent

from trip_planner.agents.specialists import critic_agent, planner_agent, refiner_agent

refinement_loop = LoopAgent(
    name="refinement_loop",
    sub_agents=[critic_agent, refiner_agent],
    max_iterations=3,
)

iterative_planner_agent = SequentialAgent(
    name="iterative_planner_agent",
    sub_agents=[planner_agent, refinement_loop],
    description="A workflow that iteratively plans and refines a trip to meet constraints.",
)
