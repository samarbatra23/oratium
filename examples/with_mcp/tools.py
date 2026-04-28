"""Function tools for the with_mcp example."""

from __future__ import annotations

from agents import function_tool


@function_tool
async def end_call() -> str:
    """End the current phone call. Use this when the conversation is complete
    and the caller has confirmed they have nothing more to discuss.
    """
    return "Call ended."


@function_tool
async def transfer_to_human(reason: str) -> str:
    """Transfer the call to a human agent. ``reason`` is a one-sentence
    summary that will be relayed to the human."""
    return f"Transfer initiated. Reason: {reason}"
