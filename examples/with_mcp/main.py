"""oratium quickstart demonstrating an MCP server + local function tools.

A single-tenant agent whose capabilities are sourced from:
- A local Python function tool (``end_call``, ``transfer_to_human``)
- Tools advertised by an HTTP MCP server

This is the simplest demonstration of the unified tool endpoint pattern
(decision 0007 in ``docs/architecture.md``): one ``UnifiedTools(...)``
collects multiple capability sources, the agent sees them as a single
function-call interface.

Run::

    pip install oratium
    export OPENAI_API_KEY=sk-...
    uvicorn examples.with_mcp.main:app --port 8421

Then expose the server with ngrok and point your Twilio number's voice
webhook at ``https://<your-host>/incoming-call``. Edit the MCP URL below
to point at your own MCP server.
"""

from __future__ import annotations

import logging

import oratium
from examples.with_mcp.tools import end_call, transfer_to_human

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


# Replace this URL with your MCP server. Easy starting points:
#   - Run a local one: `npx @modelcontextprotocol/server-everything`
#   - Build your own per the MCP spec at https://modelcontextprotocol.io
_MCP_SERVER_URL = "https://your-mcp-server.example.com"


agent = oratium.Agent(
    name="mcp-demo",
    instructions=(
        "You are an assistant on a phone call. The call has just connected."
        " Open with a brief, warm greeting. You have access to tools provided"
        " by an MCP server and two local functions: end_call (when the caller"
        " is done) and transfer_to_human (for anything you cannot handle)."
        " Keep responses concise and conversational."
    ),
    voice="alloy",
    model="gpt-4o-realtime-preview-2024-12-17",
    tools=oratium.UnifiedTools(
        functions=[end_call, transfer_to_human],
        mcp_servers=[_MCP_SERVER_URL],
    ),
)

app = oratium.OratiumApp(agent=agent)
