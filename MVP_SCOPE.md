# oratium v0 MVP — scope and build plan

This document defines the minimum viable v0 release. It is the build
plan Claude Code will follow.

## v0 success criteria

A developer with no prior context clones the repo, runs three commands,
and within 30 minutes has:

1. A multi-tenant voice agent service running locally
2. Two example tenants with different agent prompts and tools
3. A working Twilio number connected to one tenant
4. Logs streaming, traces visible, basic metrics exposed
5. Tests passing with 80%+ coverage on core logic

If any of those is not true at v0, v0 is not done.

## What ships in v0

### Core: `oratium` package

```
oratium/
├── __init__.py
├── agent.py              # Agent wrapper around OpenAI Agents SDK
├── app.py                # OratiumApp — FastAPI app factory
├── tenant.py             # Tenant model, loading, isolation
├── config.py             # Config loading (env, file, DB)
├── tools/
│   ├── __init__.py
│   ├── unified.py        # UnifiedTools dispatcher
│   ├── knowledge.py      # Knowledge source as function call
│   ├── mcp.py            # MCP server as function call
│   ├── data_tables.py    # Data table queries as function call
│   └── functions.py      # Plain Python functions as tools
├── transport/
│   ├── __init__.py
│   └── twilio.py         # Twilio webhook + media stream handler
├── secrets/
│   ├── __init__.py
│   └── fernet.py         # Fernet encryption for secrets at rest
├── storage/
│   ├── __init__.py
│   ├── postgres.py       # Postgres for tenant config
│   ├── redis.py          # Redis for session state
│   └── sqlite.py         # SQLite fallback for dev / quickstart
├── observability/
│   ├── __init__.py
│   ├── logging.py        # Structured logging setup
│   └── tracing.py        # OpenTelemetry setup
└── reliability/
    ├── __init__.py
    ├── fallback.py       # Graceful fallback when LLM unavailable
    └── circuit.py        # Circuit breaker for tool calls
```

### Examples

```
examples/
├── quickstart/           # 5-minute single-tenant example from README
│   ├── main.py
│   └── README.md
├── multi_tenant/         # Two tenants, different prompts and tools
│   ├── main.py
│   ├── tenants.yaml
│   └── README.md
└── with_mcp/             # Tenant with an MCP server connected
    ├── main.py
    └── README.md
```

### Tests

```
tests/
├── conftest.py
├── test_agent.py
├── test_tenant.py
├── test_unified_tools.py
├── test_knowledge.py
├── test_mcp.py
├── test_twilio_transport.py
├── test_secrets.py
├── test_storage.py
├── test_fallback.py
└── integration/
    ├── test_quickstart.py
    └── test_multi_tenant.py
```

### Infrastructure

```
docker/
├── docker-compose.yml    # Postgres + Redis + oratium app
└── Dockerfile

.github/
└── workflows/
    ├── ci.yml            # Tests on PR + main
    ├── publish.yml       # PyPI publish on tag
    └── docs.yml          # Build docs

docs/
├── quickstart.md
├── multi-tenant.md
├── mcp.md
├── knowledge.md
├── llm-providers.md
├── deploy.md
└── architecture.md
```

### Documentation

- README.md (provided)
- CONTRIBUTING.md
- LICENSE (MIT)
- CHANGELOG.md (Keep a Changelog format)
- docs/ folder above

## What does NOT ship in v0

Each of these is a tempting addition. They are explicitly out of scope
for v0 and tracked for future releases.

- **SIP transport** (post-v0; Twilio Media Streams covers most adopters)
- **Jambonz adapter** (post-v0)
- **Kubernetes Helm chart** (docker-compose is sufficient for v0)
- **Web UI for tenant management** (v0 is API + config files only)
- **Custom voice provider beyond OpenAI Realtime** (OpenAI Realtime is
  the only viable speech-to-speech model at v0; others fall back to
  pipeline mode which is post-v0)
- **Workflows DSL** (data tables, MCP, and function tools cover v0
  needs; workflows can be expressed via handoffs in OpenAI Agents SDK)
- **Advanced analytics dashboard** (structured logs are enough for v0)
- **AWS Secrets Manager / Vault integration** (Fernet covers v0)
- **Live-agent escalation via SIP transfer** (basic transfer-to-number
  is in; warm transfer with context handoff is post-v0)
- **Auto-provisioning of telephony numbers** (manual config in v0)

## Build phases

Phases are ordered. Each phase ends with passing tests, working
examples, and clean commit history. Do not start phase N+1 before
phase N is committed.

### Phase 0 — repo setup (1 day)

- Create GitHub repo (public from day 1, MIT license)
- Reserve `oratium` on PyPI (already verified clean via `nameisok`)
- Set up pyproject.toml with `openai-agents`, `fastapi`, `uvicorn`,
  `pydantic`, `cryptography`, `psycopg`, `redis`, `pytest`,
  `pytest-asyncio`, `pytest-cov`, `opentelemetry-api`,
  `opentelemetry-sdk`
- Pre-commit hooks: ruff, black, mypy
- GitHub Actions: CI on PR + main
- Empty README replaced with the README.md from this handoff

### Phase 1 — minimal Twilio + Realtime loop (2–3 days)

- `oratium/transport/twilio.py`: webhook + media stream handler using
  `TwilioRealtimeTransportLayer` from `@openai/agents-extensions`
  (Python equivalent: `agents.realtime` + Twilio adapter). Verify the
  Python SDK's Twilio support during this phase — if it lags TS,
  document the gap and either contribute upstream or implement the
  transport layer manually following the SDK's transport interface.
- `oratium/agent.py`: thin wrapper around OpenAI Agents SDK `Agent` and
  `RealtimeSession`
- `oratium/app.py`: `OratiumApp` factory that builds a FastAPI app with the
  Twilio webhook routes
- `examples/quickstart/`: end-to-end working example
- Tests for the webhook and session lifecycle
- A developer can clone, set OPENAI_API_KEY + Twilio credentials,
  run uvicorn, and answer a phone call. End of phase 1 = quickstart
  works.

### Phase 2 — multi-tenant config (3–4 days)

- `oratium/tenant.py`: Tenant pydantic model, loading from YAML/JSON/DB
- `oratium/storage/postgres.py`: tenant config in Postgres (migrations
  via Alembic)
- `oratium/storage/sqlite.py`: same interface, SQLite-backed for dev
- `oratium/config.py`: env + file + DB config resolution
- Tenant resolution from incoming Twilio number → tenant ID → config
- `examples/multi_tenant/`: two tenants with distinct prompts
- Tests for tenant resolution, config loading, isolation
- End of phase 2 = two phone numbers route to two distinct agents
  with different prompts.

### Phase 3 — secrets + Redis sessions (2 days)

- `oratium/secrets/fernet.py`: Fernet wrapper, key from env, encrypted-at-
  rest in Postgres
- `oratium/storage/redis.py`: session state with TTL
- Tenant secrets (e.g., per-tenant OpenAI key, per-tenant tool
  credentials) decrypted at runtime only
- Tests
- End of phase 3 = a tenant config with encrypted secrets round-trips
  cleanly; sessions survive process restart.

### Phase 4 — unified tool endpoint (4–5 days)

- `oratium/tools/unified.py`: `UnifiedTools` class. Accepts heterogeneous
  capability sources. Exposes a single function-call interface to the
  agent.
- `oratium/tools/functions.py`: plain Python function tools (delegate to
  OpenAI Agents SDK)
- `oratium/tools/knowledge.py`: knowledge sources as function calls.
  v0 supports local PDF and web URL ingestion → simple RAG → function
  call tool definition.
- `oratium/tools/data_tables.py`: structured data queries as function
  calls. Tenant defines named tables; agent can query by parameters.
- `oratium/tools/mcp.py`: MCP server connection. Discover tools at
  startup. Expose each as a function call. Handle MCP server failure.
- `examples/with_mcp/`: tenant with one MCP server
- Tests for each tool type and the unified dispatcher
- End of phase 4 = an agent can answer questions using a PDF, query
  a data table, and call an MCP server tool, all via the same
  function-call interface.

### Phase 5 — observability + reliability (2–3 days)

- `oratium/observability/logging.py`: structured JSON logs with tenant
  ID, session ID, call ID
- `oratium/observability/tracing.py`: OpenTelemetry spans for inference,
  tool execution, transport. OTLP exporter, configurable backend.
- `oratium/reliability/fallback.py`: when OpenAI Realtime call fails or
  the agent returns 4xx/5xx, transfer to a configured fallback number
  during business hours OR play a "please try again" message. Tenant-
  configurable.
- `oratium/reliability/circuit.py`: circuit breaker for individual tool
  calls so a flaky MCP server doesn't bring down all calls
- Tests
- End of phase 5 = forced failures produce clean fallback behavior;
  traces are visible in a local Jaeger.

### Phase 6 — docs, polish, release (3–4 days)

- All docs/ pages written
- CONTRIBUTING.md complete
- CHANGELOG.md initialized
- Example docker-compose stack documented
- Coverage at 80%+ on `oratium/` (excluding `examples/`)
- Tag v0.1.0
- Publish to PyPI
- Public announcement: Hacker News (Show HN), r/MachineLearning,
  r/voicetech, voice AI Discords/Slacks. Tweet thread. Post to
  /r/Twilio and the OpenAI dev forum.
- Update LinkedIn and GitHub profiles to feature the project

## Total v0 timeline

~3 weeks of focused effort (assuming 10–15 hours/week). Realistic
calendar time: 4–6 weeks.

## Beyond v0 — v0.2 to v1 milestones

Tracked in [GitHub Issues][issues] (created during phase 0). High-level:

- **v0.2** (month 2): SIP transport, AWS Secrets Manager backend
- **v0.3** (month 3): Jambonz adapter, additional knowledge backends
  (Pinecone, Weaviate)
- **v0.4** (month 4): Helm chart, Kubernetes deployment guide,
  Datadog/New Relic observability backends
- **v0.5** (month 5): Workflow DSL, warm transfer with context
- **v1.0** (month 6): production-stability release, first round of
  external contributors merged, "Used by" list with 2–3 logos

## Decision log

When you make a non-obvious decision, append to docs/architecture.md
in this format:

```
## YYYY-MM-DD — <decision title>

**Context**: <what was the situation>
**Decision**: <what was chosen>
**Alternatives considered**: <what was rejected and why>
**Consequences**: <what this enables/forecloses>
```

This is for two reasons. First, future contributors need to understand
why things are the way they are. Second, for the immigration evidence
package, a decision log is concrete proof of architectural ownership.

## Quality bar

Every PR (including from the author) must:

- Pass CI (tests + lint + type check)
- Have tests for new logic
- Have docstrings on public functions
- Update CHANGELOG.md if the change is user-facing
- Update relevant docs/ page if behavior changes

No exceptions. The bar is "I would be proud to show this to a senior
engineer at a fintech I want to work for." If that's not true, fix it
before merging.

[issues]: https://github.com/samarbatra23/oratium/issues
