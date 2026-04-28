# oratium architecture decisions

This is the project's decision log. Every non-obvious architectural choice — any
choice where two reasonable engineers might disagree — is recorded here as a
numbered entry with context, decision, alternatives considered, and consequences.

This serves two audiences. Future contributors need to understand *why* things
are the way they are; "git blame plus commit history" is rarely sufficient. And,
separately, the log is concrete evidence of architectural ownership for the
project's public narrative.

New entries are appended in chronological order. Entries are not edited in place
once committed; if a decision is later reversed or superseded, a new entry
records that and references the prior one.

---

## 0001 — Twilio Media Streams transport: build vs. upstream vs. polyglot

**Date:** 2026-04-28

**Context.** v0 ships Twilio Media Streams as the default telephony layer (per
`MVP_SCOPE.md`, Phase 1). The OpenAI Agents JS SDK ships a packaged
`TwilioRealtimeTransportLayer` in `@openai/agents-extensions` that handles audio
format transcoding (μ-law 8 kHz ↔ PCM 24 kHz), Twilio mark-event interruption
timing, and audio forwarding. The Python SDK does not have an equivalent class.
It ships only example code in `examples/realtime/twilio/twilio_handler.py`, plus
a SIP-attach example in `examples/realtime/twilio_sip/server.py`. To use Twilio
Media Streams from Python today, the integrator writes the websocket handler
themselves, talking to `OpenAIRealtimeWebSocketModel` underneath. This is a gap
that materially affects oratium's Phase 1.

**Decision.** Build the transport in oratium as a first-class component:
`oratium.transport.twilio.TwilioMediaStreamTransport` (or near equivalent),
hardening the pattern from the official Python example into a tested,
documented, public API surface. Internally it uses
`OpenAIRealtimeWebSocketModel`. Externally, it is designed so that a future
official Python `TwilioRealtimeTransportLayer` (or equivalent) can be swapped in
by re-implementing oratium's class to delegate to the upstream adapter, without
breaking any oratium consumer's import path or behavior.

**Alternatives considered.**

- **Contribute upstream to `openai-agents-python` first.** Build the Python
  equivalent of `TwilioRealtimeTransportLayer` as a PR to the upstream SDK and
  consume it from oratium once merged. Strictly higher value to the ecosystem,
  but introduces hard schedule risk that the project does not control:
  maintainer dialogue, design alignment, and review velocity. Rejected as the
  *blocking* path for v0; retained as a separate, post-v0 workstream.

- **Polyglot bridge to the JS adapter.** Run the JS
  `TwilioRealtimeTransportLayer` in a Node.js sidecar and have oratium's Python
  core talk to it over gRPC or HTTP. Would reuse a working, beta-tested
  transport without writing one. Rejected: violates the Python-core stack
  decision, adds inter-process latency on a real-time voice path where
  milliseconds matter, doubles the runtime dependency surface for adopters, and
  fights the project's preference for boring, standard, well-documented
  choices.

**Consequences.**

- oratium owns the maintenance of this transport class until upstream ships a
  Python adapter. We accept that maintenance cost; in return we control the
  ergonomics, can fix bugs at our own pace, and use it as a contribution in its
  own right.
- The class is treated as part of oratium's public API surface from day one:
  documented, with a stable signature, and pluggable behind the same interface
  as future transports (SIP, Jambonz). The "Pluggable everything" promise in
  the README applies to this layer.
- A separate post-v0 workstream will extract a generalized version of this
  transport and propose it upstream to `openai-agents-python`. If that PR
  lands, oratium re-implements its class to delegate to the upstream adapter,
  preserving all import paths and observed behavior.
- Phase 1 includes a smoke-test deliverable: before lifting the pattern from
  `examples/realtime/twilio/twilio_handler.py`, verify the example still works
  end-to-end against the current `openai-agents` version. The SDK is in beta
  and behavior may have shifted since the example was written.

---

## 0002 — Phase 1 public API surface

**Date:** 2026-04-28

**Context.** Phase 1 ships the first public API surface adopters will see:
`oratium.Agent`, `oratium.OratiumApp`, and
`oratium.transport.twilio.TwilioMediaStreamTransport`. The shape of these
classes constrains every later phase. The README quickstart promises that
`app = OratiumApp(agent=agent)` works as an ASGI app for uvicorn; the
docstrings promise the transport class is pluggable when an upstream Python
adapter ships (decision 0001). The SDK smoke-test (decision 0001's deliverable)
also revealed that `agents.realtime.RealtimeAgent` does not accept a `voice`
argument — voice belongs in the per-session `model_config` — so the wrapper
shape is forced.

**Decision.** Three small, opinionated classes with these contracts:

- **`oratium.Agent`** is a regular dataclass holding `name`, `instructions`,
  `voice`, `tools`, `model`. It exposes `to_realtime_agent()` to produce the
  underlying SDK `RealtimeAgent` and `model_config(api_key, playback_tracker)`
  to produce the dict consumed by `RealtimeRunner.run`. Voice and model live
  here even though they are applied at session-creation time, because that is
  where adopters expect them in the public API.

- **`oratium.transport.twilio.TwilioMediaStreamTransport`** *receives* an
  already-configured `RealtimeSession` and `RealtimePlaybackTracker`; it does
  not create them. `run()` is a single async method that accepts the
  websocket, then concurrently runs three loops via `asyncio.TaskGroup`:
  (1) Twilio messages → session, (2) session events → Twilio, (3) periodic
  buffer flush. Audio passes through as G.711 μ-law on both sides — both
  Twilio and OpenAI Realtime accept it natively, so no transcoding layer.
  Event dispatch uses `isinstance(event, RealtimeAudio | RealtimeAudioInterrupted)`
  rather than string-type matching, for type narrowing under mypy.

- **`oratium.OratiumApp`** holds an internal FastAPI instance and implements
  `__call__(scope, receive, send)` so the instance itself is an ASGI app.
  This is what enables the README's `uvicorn module:app` pattern with
  `app = OratiumApp(agent=agent)`. The websocket handler creates a session
  per call and delegates to `TwilioMediaStreamTransport.run()`.

**Alternatives considered.**

- **Transport creates its own session** (instead of receiving one). Simpler
  one-class API but couples the transport to API-key and agent concerns and
  makes the upstream-swap path harder. Rejected — separation of concerns
  beats one-class convenience here, especially given the upstream-swap
  invariant from decision 0001.

- **Match events on `event.type == "audio"` strings** (the SDK example's
  pattern) instead of `isinstance`. Slightly shorter; works at runtime.
  Rejected because mypy can narrow `isinstance` checks but not Literal
  string comparisons in our union, and we want type-safety on event handling.

- **Subclass FastAPI from OratiumApp.** Simplest possible "uvicorn just works"
  pattern. Rejected because it leaks every FastAPI method onto the oratium
  surface and pins us to FastAPI internals; composition with `__call__`
  delegation is cleaner and gives us `OratiumApp.fastapi` for users who need
  the underlying instance.

- **Return TwiML from `incoming-call` as a Pydantic model.** Rejected — TwiML
  is XML; we return a `PlainTextResponse(media_type="text/xml")` directly.

**Consequences.**

- The transport class is genuinely pluggable. The day OpenAI ships a Python
  `TwilioRealtimeTransportLayer`, decision 0001's swap path is: keep
  `TwilioMediaStreamTransport` as the import name, replace its body with a
  thin wrapper that delegates to the upstream class, ship a deprecation note
  pointing at the upstream import. Adopters never see a breaking change.
- The websocket handler in `OratiumApp` is small but exercises real SDK
  surfaces (`RealtimeRunner`, `RealtimeSession.enter`, `await transport.run()`).
  Unit-testing it would mostly exercise the SDK rather than oratium logic, so
  it is marked `# pragma: no cover` for Phase 1; integration coverage comes
  from the quickstart example. Phase 4+ may add an integration test that
  mocks the SDK.
- Audio passthrough (no transcoding) means oratium has zero CPU cost for
  audio. If a future telephony layer doesn't support μ-law, the transcoding
  responsibility falls on that transport's adapter, not on oratium core.
- `oratium.Agent` is intentionally separate from `agents.realtime.RealtimeAgent`.
  Phase 4's `UnifiedTools` layer will plug in here without changing
  `RealtimeAgent`'s shape.

---

## 0003 — Agent greeting trigger on call connect

**Date:** 2026-04-28

**Context.** First end-to-end Twilio call against the Phase 1 quickstart
revealed two facts the unit-tested paths could not surface: OpenAI Realtime
does not generate a response until it receives input (turn detection waits
for user audio), so the call connected silently. The reference SDK example
masks this by playing a TwiML ``<Say>`` greeting via Twilio's TTS before the
WebSocket connects — the caller hears Twilio's robotic voice first, then the
agent's voice once they speak. For oratium, that voice-quality jump is
exactly the production-readiness gap the project is meant to close.

**Decision.** After ``session.enter()`` and before handing control to
``TwilioMediaStreamTransport.run()``, the websocket handler in
``OratiumApp`` calls ``session.send_message("Hello")`` to nudge the model
into producing an immediate response. The agent's ``instructions`` string
is responsible for the actual greeting content; the nudge only triggers
the turn. The caller hears the agent's configured voice from the very first
syllable — no TTS hand-off.

**Alternatives considered.**

- **TwiML ``<Say>`` greeting (the SDK example pattern).** Reliable: plays
  even if the WebSocket is slow to negotiate. Rejected because the
  voice-quality jump from Twilio TTS to the agent voice is jarring and
  signals "demo" not "production." A real production deployment is
  expected to keep voice consistent end-to-end.

- **Lower-level ``response.create`` event via ``RealtimeModelSendRawMessage``.**
  Cleanest from a transcript perspective (no fake user "Hello" appears in
  the conversation history). Rejected because it depends on internal SDK
  surfaces that may shift between versions; ``send_message`` is the
  documented public API.

- **Make greeting opt-in via an ``OratiumApp`` parameter.** Considered. Not
  every agent should greet first (debt collection, security verification,
  inbound-only agents). Deferred: for Phase 1 the trigger is unconditional
  and adopters can suppress it by writing ``instructions`` that say
  "respond with one word: 'continue'" or similar. Phase 2 (multi-tenant)
  will add a per-tenant ``greet_on_connect`` config field where this
  belongs.

**Consequences.**

- The synthetic "Hello" appears in the conversation transcript as a user
  message. Adopters who want clean transcripts will need the ``response.create``
  approach later; this is acceptable because v0 doesn't ship transcript
  export and Phase 5 observability will surface this clearly.
- Personality and lifecycle are now visibly separate concerns:
  ``Agent.instructions`` controls *what* the agent says; the websocket
  handler in ``OratiumApp`` controls *when* it speaks first. Phase 2's
  per-tenant config will give that lifecycle knob a proper home.
- Quickstart instructions tightened to anticipate the synthetic opener
  ("The call has just connected. Open with a brief, warm greeting...").
  This makes the agent's first turn read naturally instead of as a literal
  reply to the word "Hello".
- The websocket handler is still in the ``# pragma: no cover`` region per
  decision 0002. The greeting trigger was verified end-to-end with a real
  Twilio call rather than via mocked unit tests.

---

## 0004 — oratium is a library, not a platform

**Date:** 2026-04-28

**Context.** Phase 1 ships a quickstart where the agent is defined entirely
in Python (``Agent(name=..., instructions=..., voice=..., model=...)``).
Phase 2 will introduce per-tenant configuration loaded from YAML or Postgres.
Before that abstraction lands, the question that shapes every later phase is:
who is oratium *for*, and how do they configure agents? The README answers
this in the comparison table ("Hosted UI (intentionally)" as the trade-off vs
Vapi / Bland), but the architecture log has not yet captured the underlying
decision or its consequences for the API.

**Decision.** Oratium is a library for **developers**, not a platform for
**non-technical users**. Adopters configure agents in two modes:

1. **In Python code** (Phase 1 onward) — ``oratium.Agent(...)`` constructed
   in the user's application, suitable for single-tenant or programmatic
   use cases.
2. **In declarative config** (Phase 2 onward) — Pydantic-validated tenant
   definitions loaded from YAML or a database (SQLite / Postgres), suitable
   for multi-tenant deployments.

Both paths produce the same ``oratium.Agent`` object internally. There is no
admin UI, no SaaS console, no web flow for editing tenants. The audience is
engineers; the calling end-user (the person dialing the phone number) does
not configure anything.

**Alternatives considered.**

- **Bundle a web UI for tenant management.** Considered. Would broaden the
  audience to ops / non-engineers and accelerate adoption for fintech buyers
  who want a turnkey console. Rejected for v0: bundling a UI doubles the
  surface area, pulls in frontend deps that fight the "boring Python
  library" stack decision, and turns oratium into a competitor of Vapi
  rather than a building block they themselves could be built on. A separate
  ``oratium-admin`` project can supply this layer if there is real demand.

- **Become a hosted SaaS** like Vapi / Bland. Rejected as out of scope. The
  evidence value of this project comes from being an open, adoptable library
  that other developers and organizations build on — not a hosted
  competitor. SaaS is a different product with different adoption mechanics.

- **Code-only configuration (no YAML / DB).** Considered. Simplest API
  surface. Rejected: every adopter beyond a single-tenant prototype would
  need to redeploy on a tenant change, which contradicts the multi-tenancy
  contribution gap (gap 1 in ``CONTEXT.md``). YAML / DB is cheap to add and
  unlocks the production deployment shape.

**Consequences.**

- **Audience.** Documentation, examples, and design choices target software
  engineers comfortable with Python, YAML, and (for the Postgres path) a
  schema migration tool. There is no "settings UI" to optimize for.
- **Tools and capabilities** (Phase 4) split along the same line: function
  tools must be Python code (referenced from declarative config by import
  path); knowledge sources, MCP servers, and data tables can be
  config-only (URLs, paths, connection strings).
- **Scaling.** Adding a tenant in production is a config or DB change, not
  a deploy. Phase 2's tenant-resolution contract makes this explicit.
- **Future UI.** If a UI is ever wanted, it lives in a separate project
  (e.g., ``oratium-admin``) that depends on oratium. The core library
  stays focused on the runtime + storage primitives.
- **Both configuration modes coexist.** ``OratiumApp(agent=...)``
  (single-tenant, Phase 1) and ``OratiumApp(tenants=...)`` (multi-tenant,
  Phase 2) are not deprecated alternatives — they are two valid entry
  points for two valid scales. The library supports both indefinitely.

---

## 0005 — Tenant model and storage architecture

**Date:** 2026-04-28

**Context.** Phase 2 introduces multi-tenant configuration: many agents on
one oratium deployment, routed by Twilio number. This requires a tenant
model, a storage interface with several backend implementations, a tenant
resolution path through the request lifecycle, and a migration story. The
shape of these abstractions constrains every later phase — Phase 3's
secrets, Phase 4's tools, Phase 5's per-tenant observability all attach to
the same ``Tenant`` object. Decision 0004 establishes that tenant config
lives in YAML or a database, not a UI.

**Decision.**

- **Tenant model: Pydantic BaseModel** (not a dataclass like
  ``oratium.Agent``). Tenants come from external sources (YAML, DB, future
  config endpoints) and need validation; ``oratium.Agent`` is constructed
  in code by the developer and doesn't. Two different concerns. The
  ``Tenant`` model carries an ``id``, an E.164-validated ``twilio_number``,
  and an ``agent`` sub-model (``TenantAgentConfig``) with the same shape as
  ``oratium.Agent``'s public knobs. ``Tenant.to_runtime_agent()`` builds
  the runtime ``Agent`` for the websocket session.

- **Storage interface: ``TenantStore`` Protocol** (not ABC). Async methods:
  ``get_by_twilio_number``, ``get_by_id``, ``list_all``. Async even for
  in-memory backends so the OratiumApp websocket handler has one signature
  to call. Three implementations ship in v0:

  | Backend | When to use |
  | --- | --- |
  | ``YAMLTenantStore`` | Dev, single-server, ~10 tenants, redeploy on change. Config-as-code workflow. |
  | ``SQLiteTenantStore`` | Single-node prod, hundreds of tenants, no separate DB infra. Dynamic updates without redeploy. |
  | ``PostgresTenantStore`` | Multi-node prod, lots of tenants, shared state across oratium replicas. |

  All three implement the same Protocol; swapping is a one-line change in
  the OratiumApp construction.

- **Tenant routing: Twilio ``To`` parameter at the webhook, threaded
  through to the websocket via a path segment.** Twilio's POST to
  ``/incoming-call`` includes a ``To`` form field with the called E.164
  number. The webhook resolves the tenant via
  ``store.get_by_twilio_number(to)``, then generates TwiML with
  ``wss://host/media-stream/{tenant_id}`` (path segment, not query
  string — see the addendum below). The websocket handler receives the
  tenant id as a FastAPI path parameter, refetches the tenant by id, and
  builds the agent. Tenant resolution happens *once* at webhook time;
  the websocket handler trusts the resolved id.

- **Coexistence with single-tenant mode.** ``OratiumApp(agent=Agent(...))``
  (Phase 1) and ``OratiumApp(tenants=TenantStore(...))`` (Phase 2) are
  mutually exclusive constructor modes. Exactly one must be provided.
  Single-tenant mode skips the tenant lookup and uses the configured
  agent for every call. This preserves the Phase 1 quickstart unchanged.

- **SQL schema: tenants table with a JSON ``agent_config`` column** (not
  fully normalized). Agent shape (instructions, voice, model, eventually
  tools / knowledge / MCP) evolves quickly; storing it as JSON means
  schema migrations are needed for tenant-level fields (id, twilio_number,
  enabled, ...) but not for agent-shape changes. We never query *into*
  agent_config — lookup is by id or twilio_number only — so the loss of
  SQL queryability is free.

- **Postgres migrations: Alembic.** Migrations live inside the package at
  ``oratium/storage/migrations/``, so they ship to adopters with the wheel.
  An ``oratium-migrate`` console-script entry point invokes Alembic against
  the user's ``DATABASE_URL``. SQLite uses ``Base.metadata.create_all()``
  on first run — no migrations needed for an embedded DB whose schema we
  control end-to-end.

**Alternatives considered.**

- **Dataclass for Tenant (consistency with Agent).** Would lose
  Pydantic's free YAML / JSON validation and the E.164 number constraint.
  Rejected — consistency for its own sake isn't worth re-implementing
  validation by hand for every external loader.

- **Sync ``TenantStore``.** Simpler interface for the YAML case. Rejected
  — DB backends need async (asyncpg, aiosqlite), and forcing a unified
  sync interface would block the FastAPI event loop on DB queries.

- **Tenant routing via Twilio Custom Parameters in the ``<Stream>`` tag**
  (instead of URL query). More idiomatic Twilio. Rejected for v0 because
  custom parameters arrive in the ``start`` event mid-stream — the
  websocket handler would have to defer session setup until the first
  message arrives. URL query lets us resolve and validate at handshake
  time, fail fast on unknown tenants. Reconsider in a later phase if
  Custom Parameters bring something we need.

- **Look up tenant in the websocket handler instead of the webhook.** The
  websocket alone doesn't know the called number (Twilio doesn't send it
  in the WS handshake). Without webhook-side resolution, we'd need a
  Twilio API callback to look up the call by ``CallSid``, adding a
  network round trip and a Twilio API key dependency just for routing.

- **Normalize the SQL schema (one column per agent field).** Future-proof
  if we ever want to query "show me all tenants using voice X". Rejected
  — Phase 4 will add a dozen more agent fields (tool URIs, MCP servers,
  knowledge sources); migrating each one is friction. Keep it JSON until
  a real query need emerges.

- **Skip Alembic, use ``create_all()`` everywhere.** Simpler. Rejected for
  Postgres because production schema changes will happen and ad-hoc
  ``ALTER TABLE`` is unsafe. Alembic is the standard.

**Consequences.**

- **The Phase 1 quickstart keeps working.** ``OratiumApp(agent=agent)``
  remains the simplest entry point. Multi-tenant is opt-in.
- **Adding a tenant in production is a config change** (YAML edit + reload,
  or a SQL INSERT) — not a deploy. This satisfies the multi-tenancy
  contribution gap.
- **Phase 3's secrets** attach to the ``Tenant`` model as an encrypted
  field. The schema change is one new column on the tenants table —
  Alembic handles it.
- **Phase 4's tools / MCP / knowledge** attach to ``TenantAgentConfig``
  as new sub-models. Stored as JSON, no migration needed.
- **Tenant lookup is on the call-setup hot path** but happens at HTTP
  webhook time (not the WS audio loop), so latency is uncontroversial:
  one DB query per call.
- **The ``oratium-migrate`` CLI** ships with the package. Adopters running
  Postgres run it once on first boot and again after each upgrade.

**Addendum (2026-04-28, post-first-call test).** The original Phase 2
implementation used a URL query string (``?tenant={id}``) on the
``<Stream>`` URL, on the assumption that Twilio passes query strings
through to the Media Streams websocket. First end-to-end call with a real
Twilio number disproved this: the webhook routed the call correctly, but
the websocket connection arrived at ``/media-stream`` with no query
string. The fix is to use a path segment (``/media-stream/{tenant_id}``)
which Twilio reliably preserves. Implemented same-day; tests updated to
match.

---

## 0006 — Secrets at rest, per-tenant API keys, session storage

**Date:** 2026-04-28

**Context.** Phase 3 introduces two new concerns: per-tenant secrets that
must be encrypted at rest in production storage, and a session-state
primitive intended to survive a process restart. CONTEXT.md flags
encrypted credential storage as part of the production-grade reliability
contribution gap (gap 4). The existing Tenant model and TenantStore
protocol need extension without breaking Phase 1 / Phase 2 callers.

**Decision.**

- **Symmetric encryption with Fernet.** ``cryptography.Fernet`` wraps a
  key from ``$ORATIUM_FERNET_KEY`` (already documented in
  ``.env.example`` since Phase 0). ``oratium.secrets.FernetCipher``
  exposes ``encrypt`` / ``decrypt`` / ``generate_key`` plus a
  ``from_env`` classmethod. One key per deployment. Multi-key key
  rotation is post-v0.

- **Per-tenant secrets as a closed typed sub-model.**
  ``Tenant.secrets: TenantSecrets | None`` where ``TenantSecrets`` has a
  closed set of fields the runtime knows how to use. v0 ships one field:
  ``openai_api_key`` (overrides the deployment-wide ``OPENAI_API_KEY``
  for this tenant's calls). Phase 4 adds tool-specific credential
  fields. Closed model rather than open ``dict`` gives static typing at
  every call site and forces every new secret type to land as an
  explicit field — a useful forcing function.

- **Storage layer encryption is opt-in per backend.**

  | Backend | Secrets handling |
  | --- | --- |
  | YAML | Plaintext in the file. YAML lives on disk / in source control; an encrypted blob in YAML defeats the point of human-edited config. Adopters who want encrypted YAML use ``sops`` / ``ansible-vault`` outside oratium. |
  | SQLite / Postgres | Encrypted blob in a ``secrets_encrypted`` TEXT column. Encrypt on write, decrypt on read. Constructor takes an optional ``cipher: FernetCipher``; required if any tenant being written has secrets. |

  The cipher is injected at store construction; encryption is transparent
  to callers (``store.add_tenant(tenant)`` accepts a fully-decrypted
  ``Tenant``; the store handles encryption). ``get_by_*`` returns
  decrypted ``Tenant`` instances. Phase 4 / 5 stores need only handle
  plaintext.

- **Per-tenant API key applied at session creation.** When
  ``OratiumApp``'s websocket handler builds the agent's
  ``model_config``, it prefers
  ``tenant.secrets.openai_api_key`` over the deployment-wide
  ``self._api_key`` when present. Single-tenant mode unchanged.

- **Session storage in ``oratium.storage.sessions`` (not ``redis.py``).**
  ``SessionStore`` Protocol with async ``get`` / ``set`` / ``delete``
  plus TTL on writes. Two implementations:
    * ``InMemorySessionStore`` — dict + asyncio lock. Single-process,
      dev / tests.
    * ``RedisSessionStore`` — ``redis.asyncio`` client. Multi-process
      production.

  Filename ``sessions.py`` rather than the MVP_SCOPE-suggested
  ``redis.py`` because ``oratium.storage.redis`` would shadow the
  ``redis`` package import inside the same module (confusing). v0
  establishes the primitive; Phase 5's reliability work plugs in actual
  usage (call recovery on reconnect, fallback context, rate limiting).

- **Schema migration ``0002_add_secrets``.** Adds the nullable
  ``secrets_encrypted`` TEXT column. SQLite picks it up via
  ``create_all()`` for fresh dev DBs; existing dev SQLite files need to
  be deleted (it's dev — we say so in the migration's docstring).

**Alternatives considered.**

- **AWS Secrets Manager / Vault as the storage backend.** Better for
  production-grade secret rotation. Out of scope for v0 (MVP_SCOPE
  explicitly defers it). Adopters who need it can populate
  ``tenant.secrets`` from their backend at boot, layered on top of
  oratium.

- **Open dict for secrets** (``secrets: dict[str, str]``). More flexible
  for ad-hoc Phase 4 needs. Rejected — closed model gives static typing
  at the call site (``tenant.secrets.openai_api_key`` is type-checked,
  ``tenant.secrets["openai_api_key"]`` is not) and forces every new
  secret type to land an explicit field with explicit handling.

- **Per-field column encryption** (one DB column per secret). Lets us
  ask "does this tenant have a custom OpenAI key?" without decryption.
  Rejected — Phase 4 will add many more secret fields and adding /
  migrating each one is friction; a single encrypted blob is simpler
  and the "does this exist" query has no clear consumer.

- **Filename ``oratium/storage/redis.py``.** Matches MVP_SCOPE wording
  exactly. Rejected because ``import redis`` from within
  ``oratium.storage.redis`` resolves to the local module, not the
  library. ``sessions.py`` is clearer about the abstraction
  ("I'm a session store") and the file's contents.

**Consequences.**

- The ``TenantStore`` protocol shape is unchanged. Encryption is an
  implementation detail of SQL stores. Phase 4 / 5 contributions can
  treat ``Tenant`` as plaintext throughout.
- ``examples/multi_tenant/tenants.example.yaml`` grows a commented
  ``secrets:`` block showing the shape so adopters see it without
  needing to read decision 0006.
- A deployment can mix tenants on different OpenAI accounts on one
  oratium instance — useful for agency / consultancy patterns.
- The session store is unused in Phase 3 application code. It sits
  ready for Phase 5 to wire up resilience (reconnect with context,
  fallback routing, rate limiting per-call-id).
- ``ORATIUM_FERNET_KEY`` becomes load-bearing for any deployment using
  encrypted secrets. We document the
  ``python -c "from cryptography.fernet import Fernet;
  print(Fernet.generate_key().decode())"`` recipe in
  ``.env.example`` (already there since Phase 0).
