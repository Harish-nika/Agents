"""Agent-as-Tool helpers for the trip data concierge hierarchy."""

from __future__ import annotations

from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool


async def call_db_agent(
    question: str,
    tool_context: ToolContext,
):
    """
    Use this tool FIRST to connect to the database and retrieve a list of places, like hotels or landmarks.
    """
    from trip_planner.agents.concierge_team import db_agent

    print("--- TOOL CALL: call_db_agent ---")
    agent_tool = AgentTool(agent=db_agent)
    db_agent_output = await agent_tool.run_async(
        args={"request": question}, tool_context=tool_context
    )
    tool_context.state["retrieved_data"] = db_agent_output
    return db_agent_output


async def call_concierge_agent(
    question: str,
    tool_context: ToolContext,
):
    """
    After getting data with call_db_agent, use this tool to get travel advice, opinions, or recommendations.
    """
    from trip_planner.agents.concierge_team import concierge_agent

    print("--- TOOL CALL: call_concierge_agent ---")
    input_data = tool_context.state.get("retrieved_data", "No data found.")
    question_with_data = f"""
    Context: The database returned the following data: {input_data}

    User's Request: {question}
    """

    agent_tool = AgentTool(agent=concierge_agent)
    concierge_output = await agent_tool.run_async(
        args={"request": question_with_data}, tool_context=tool_context
    )
    return concierge_output
