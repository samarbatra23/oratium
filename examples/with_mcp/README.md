# oratium with an MCP server

A single-tenant agent whose tool surface combines:

- **Two local function tools** (`end_call`, `transfer_to_human`) defined in
  Python
- **All tools advertised by an MCP server** (URL configured in `main.py`)

Demonstrates `oratium.UnifiedTools` — the unified tool endpoint pattern
(decision 0007 in [`docs/architecture.md`](../../docs/architecture.md)).
The agent doesn't know or care that some tools come from local Python and
others from a remote MCP server — they all flow through one function-call
interface.

## Prerequisites

- Same as the [single-tenant quickstart](../quickstart/README.md)
- An HTTP MCP server. A few options:
  - **Local test server:** `npx @modelcontextprotocol/server-everything`
    runs the spec's reference implementation on `http://localhost:3001`.
  - **Public test servers:** check
    [modelcontextprotocol.io](https://modelcontextprotocol.io) for a list.
  - **Your own:** build per the [MCP spec](https://modelcontextprotocol.io).

## Setup

1. **Edit `examples/with_mcp/main.py`** — replace `_MCP_SERVER_URL` with
   the URL of your MCP server. For a local server use the public address
   ngrok gives that server (your phone-facing oratium and the MCP server
   need to be reachable from each other in some way; for local-only
   testing both can run on `localhost`).

2. **Set credentials and start the server:**

   ```bash
   export OPENAI_API_KEY=sk-...
   uvicorn examples.with_mcp.main:app --port 8421
   ```

3. **Expose via ngrok:**

   ```bash
   ngrok http 8421
   ```

4. **Point Twilio at oratium** — same flow as the quickstart: paste the
   ngrok URL + `/incoming-call` into your Twilio number's Voice webhook.

5. **Call the number.** The agent now has access to:
   - `end_call()` — local
   - `transfer_to_human(reason)` — local
   - Whatever tools the MCP server advertises — discovered at session
     start

## How `UnifiedTools` desugars

When the call connects, oratium builds the runtime agent like this:

```python
runtime_agent = RealtimeAgent(
    name="mcp-demo",
    instructions="...",
    tools=[end_call, transfer_to_human],   # function tools
    mcp_servers=[MCPServerStreamableHttp(params={"url": _MCP_SERVER_URL})],
)
```

You don't write that — `UnifiedTools.to_realtime_tools()` and
`.to_mcp_servers()` produce the right shapes for the SDK. The SDK
discovers MCP tools at session start and includes them in the agent's
tool surface alongside the local ones.

## Adding more tool types

Knowledge sources (PDFs / URLs) and data tables work the same way:

```python
tools=oratium.UnifiedTools(
    functions=[end_call, transfer_to_human],
    mcp_servers=["https://my-mcp.example.com"],
    knowledge=["./policies.pdf", "https://docs.example.com/faq"],
    data_tables=[
        oratium.DataTable(name="customers", rows=[{"id": "C1", "tier": "gold"}]),
    ],
)
```

The agent gets four kinds of tools through one config schema. See
[`docs/architecture.md`](../../docs/architecture.md) decision 0007 for
the design rationale.
