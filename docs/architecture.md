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
