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
