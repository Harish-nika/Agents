"""Loop control tool for LoopAgent refinement workflows."""

from __future__ import annotations

from google.adk.tools import ToolContext

COMPLETION_PHRASE = "The plan is feasible and meets all constraints."


def exit_loop(tool_context: ToolContext):
    """Call this function ONLY when the plan is approved, signaling the loop should end."""
    print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
    tool_context.actions.escalate = True
    return {}
