# oratium

> A production-grade, multi-tenant, MCP-native voice agent framework
> built on the OpenAI Agents SDK. Pluggable everything.

[![PyPI](https://img.shields.io/pypi/v/oratium)](https://pypi.org/project/oratium/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## What this is

`oratium` is an opinionated framework for building real-time voice agents
that run in production. It wraps the [OpenAI Agents SDK][agents-sdk]
with the layers most teams end up rebuilding — multi-tenant config,
unified tool/knowledge/MCP dispatch, encrypted secrets, structured
observability, and graceful failure handling.

If you've followed a Twilio + OpenAI Realtime tutorial and then asked
"okay but how do I actually run this for ten clients with different
configurations, fallback paths, and tools that aren't function calls"
— this is the answer to that question.

## What this is not

- **Not a tutorial.** It is a library you depend on, not example code
  you copy-paste.
- **Not a wrapper that hides the SDK.** You still have full access to
  `Agent`, `RealtimeSession`, handoffs, and guardrails. `oratium` adds
  layers, it doesn't replace them.
- **Not yet another agent framework.** The agent layer is OpenAI Agents
  SDK. `oratium` is the multi-tenant production scaffolding *around* it.

## Why this exists

Real-time voice agents are no longer experimental. Banks, healthcare
providers, and customer service platforms are deploying them in
production. The infrastructure to do this safely — multi-tenant
isolation, encrypted credential storage, MCP server integration, fall-
back when the LLM is unavailable — gets rebuilt by every team that
deploys one.

`oratium` is that infrastructure, factored out and made open.

## Five things that make `oratium` different

### 1. Multi-tenant by default

Per-tenant agent definitions, voice settings, knowledge sources, and
secrets. Tenants are isolated at the config and storage layers. Adding
a new tenant is a config change, not a deploy.

### 2. Unified tool endpoint

Custom tools, knowledge bases (PDF/web/structured), MCP servers, data
table queries, and workflows all flow through a single function-call
interface to the agent. Add a new capability type to the platform once;
all voice agents inherit it without adapter changes.

```python
from oratium import Agent, UnifiedTools

agent = Agent(
    name="support",
    tools=UnifiedTools(
        knowledge=["s3://bucket/policies.pdf"],
        mcp_servers=["https://my-mcp-server.example.com"],
        data_tables=["customers", "orders"],
        functions=[transfer_to_human, end_call],
    ),
)
```

### 3. First-class MCP support

MCP servers aren't a plugin — they are a built-in capability type. Add
an MCP server URL, the agent gets its tools at runtime. Auth,
discovery, and tool registration are handled.

### 4. Pluggable everything

| Layer            | Default                       | Pluggable to                          |
| ---------------- | ----------------------------- | ------------------------------------- |
| LLM              | OpenAI Realtime               | Any LiteLLM-supported provider        |
| Telephony        | Twilio Media Streams          | SIP, Jambonz (planned)                |
| Knowledge source | Local PDF + web crawl         | Pinecone, Weaviate, custom            |
| Storage          | PostgreSQL + Redis            | SQLite (dev), custom backends         |
| Observability    | OpenTelemetry + structured logs | Datadog, New Relic, custom         |
| Secrets          | Fernet (in Postgres)          | AWS Secrets Manager, Vault (planned)  |

### 5. Production-grade reliability

- Graceful fallback when OpenAI Realtime is unavailable (transfer to
  human or play hold message — configurable per tenant)
- Tool call failure handling with retry and circuit breaker
- Call interruption detection that doesn't lose context
- Pre-signed S3 URLs for call recordings with configurable retention

## Installation

```bash
pip install oratium
```

## 5-minute quickstart

```python
import os
from oratium import Agent, OratiumApp, UnifiedTools

agent = Agent(
    name="hello-world",
    instructions="You are a helpful assistant. Greet the caller warmly.",
    voice="alloy",
)

app = OratiumApp(agent=agent)

# Run with: uvicorn quickstart:app --port 8000
# Then point your Twilio number's voice webhook to:
# https://your-host/incoming-call
```

That's a single-tenant agent. For multi-tenant, knowledge bases, MCP
servers, and the rest, see the [full quickstart][quickstart].

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Telephony Layer                                         │
│  Twilio Media Streams (default) | SIP | Jambonz adapter │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  Voice Transport (OpenAI Agents SDK)                     │
│  TwilioRealtimeTransportLayer | RealtimeSession          │
│  Interruption handling | Turn detection | Audio routing  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  Agent Layer (OpenAI Agents SDK)                         │
│  Agent | Handoffs | Guardrails | Sessions                │
│  ─ pluggable LLM provider via LiteLLM extension          │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  Unified Tool Endpoint                        (oratium) │
│  Single function-call interface exposing:                │
│    • Custom tools                                         │
│    • Knowledge hubs (PDF, web, structured)               │
│    • MCP servers                                          │
│    • Data tables / DB queries                            │
│    • Workflows                                            │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  Tenant & Config Layer                        (oratium) │
│  Per-tenant agent config | Multi-tenant isolation         │
│  Encrypted secrets | Runtime config retrieval             │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  Observability & Reliability                  (oratium) │
│  Structured logs | Tracing (OTel) | Failure handling     │
│  Graceful fallback | Live-agent escalation               │
└─────────────────────────────────────────────────────────┘
```

The OpenAI Agents SDK provides layers 2–3. `oratium` provides layers 4–6
plus a clean integration with layer 1.

## Comparison to alternatives

| Project                  | What it gives you                      | What it doesn't                                    |
| ------------------------ | -------------------------------------- | -------------------------------------------------- |
| Twilio's official sample | Single-tenant Realtime + Twilio loop   | Multi-tenancy, MCP, knowledge, observability      |
| OpenAI Agents SDK alone  | Agent, handoffs, transport             | Multi-tenancy, knowledge, MCP, secrets, deploy    |
| LangChain / LangGraph    | General agent toolkit                  | Real-time voice transport, multi-tenancy primitives |
| Vapi / Bland (hosted)    | Managed service, faster to start       | Self-hosting, code-level control, no vendor lock  |
| `oratium`                    | All of the above as a self-host stack  | Hosted UI (intentionally)                         |

## Documentation

- [Quickstart][quickstart]
- [Multi-tenant guide][multi-tenant]
- [Adding an MCP server][mcp-guide]
- [Knowledge sources][knowledge-guide]
- [Pluggable LLM providers][llm-guide]
- [Production deployment][deploy-guide]

## Used by

> If you're using `oratium` in production or evaluation, please open a PR
> adding your organization here. Logos welcome. This is the section
> that helps the project — and other adopters — most.

_Be the first._

## Contributing

PRs welcome. The contribution areas with the highest leverage right now:

- Additional LLM provider tested via LiteLLM
- SIP transport adapter (post-v0)
- Knowledge source adapters (Pinecone, Weaviate, etc.)
- Observability backend adapters (Datadog, New Relic)
- Documentation, examples, real-world deployment guides

See [CONTRIBUTING.md][contributing] for the full guide.

## License

MIT. See [LICENSE](./LICENSE).

## Related work

This project is the open-source companion to a series of articles on
production voice agent architecture. See [the writeup][article] for the
design rationale behind the unified tool endpoint and multi-tenant
config layer.

---

[agents-sdk]: https://openai.github.io/openai-agents-python/
[quickstart]: ./docs/quickstart.md
[multi-tenant]: ./docs/multi-tenant.md
[mcp-guide]: ./docs/mcp.md
[knowledge-guide]: ./docs/knowledge.md
[llm-guide]: ./docs/llm-providers.md
[deploy-guide]: ./docs/deploy.md
[contributing]: ./CONTRIBUTING.md
[article]: # "TODO: link to companion article when published"
