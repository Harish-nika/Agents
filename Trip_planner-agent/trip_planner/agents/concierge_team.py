"""Concierge hierarchy: mock DB + food critic + orchestrator."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

from trip_planner.config import MODEL_NAME
from trip_planner.prompts.concierge import (
    CONCIERGE_INSTRUCTION,
    DB_AGENT_INSTRUCTION,
    FOOD_CRITIC_INSTRUCTION,
    TRIP_DATA_CONCIERGE_DESCRIPTION,
    TRIP_DATA_CONCIERGE_INSTRUCTION,
)
from trip_planner.tools.agent_tools import call_concierge_agent, call_db_agent

db_agent = Agent(
    name="db_agent",
    model=MODEL_NAME,
    instruction=DB_AGENT_INSTRUCTION,
)

food_critic_agent = Agent(
    name="food_critic_agent",
    model=MODEL_NAME,
    instruction=FOOD_CRITIC_INSTRUCTION,
)

concierge_agent = Agent(
    name="concierge_agent",
    model=MODEL_NAME,
    instruction=CONCIERGE_INSTRUCTION,
    tools=[AgentTool(agent=food_critic_agent)],
)

trip_data_concierge = Agent(
    name="trip_data_concierge",
    model=MODEL_NAME,
    description=TRIP_DATA_CONCIERGE_DESCRIPTION,
    tools=[call_db_agent, call_concierge_agent],
    instruction=TRIP_DATA_CONCIERGE_INSTRUCTION,
)
