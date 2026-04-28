# Project Context — For Claude Code

## What this document is

This is the master context document for an open-source project being built
to support an EB-2 National Interest Waiver (NIW) immigration petition.
Read this first before touching any code. The README and MVP scope sit
alongside this file and describe the technical project. This document
explains *why* the project exists, who is building it, and how technical
decisions should be evaluated against the immigration-evidence goal.

If you only read one section, read "How to evaluate trade-offs" at the end.

---

## The author

Samar Batra. Indian-born, currently on H-1B in the US. Software Engineer
at Kasisto Inc. since February 2023. Master of Science in Data Science,
SUNY Buffalo (3.9/4.0). AWS internship 2022. Four years prior at Octro
(gaming) in India before grad school.

At Kasisto, Samar has built voice AI infrastructure for U.S. consumer
banking. Past 15 weeks specifically: architected a real-time speech-to-
speech voice agent integrating OpenAI Realtime + Twilio (eliminating
STT/TTS pipeline latency), designed a unified-tool-endpoint pattern for
agent capabilities, migrated multiple adapters into the platform with
zero-trust service-to-service auth, productionized three multi-tenant
debt collection voice agents (MassDOT, NJSP, Boston DOT) for Duncan
Solutions, built Microsoft A365 / Teams integration, and shipped voice-
channel configuration with multi-provider support (Deepgram, ElevenLabs,
Google, Microsoft, OpenAI).

This open-source project is the reference implementation of those
architectural patterns, built from scratch outside Kasisto's IP.

## The goal — be specific

Samar is pursuing EB-2 NIW. India-born applicants face a 12+ year EB-2
backlog, so the NIW priority date is precious — file early, file with
strong evidence. Plan: build profile for 6–12 months, then file via
Manifest Law (an immigration firm specializing in tech profiles).

NIW approval requires meeting the *Matter of Dhanasar* three-prong test:
1. The proposed endeavor has substantial merit and national importance
2. The applicant is well-positioned to advance the endeavor
3. On balance, it would benefit the U.S. to waive labor certification

Samar's framed endeavor: "advancing secure conversational and voice-based
AI infrastructure for U.S. consumer banking — with focus on real-time
voice agents handling sensitive financial interactions, enabling smaller
financial institutions to access AI capabilities previously reserved for
large banks, while strengthening fraud resilience, accessibility for
underbanked populations, and reducing systemic operational risk."

Beyond NIW, this project also builds toward EB-1A (Extraordinary Ability)
in 2–3 years, which has a much shorter India backlog (~3 years vs 12+).
EB-1A criteria this project supports:
- Original contributions of major significance (the architecture itself)
- Authorship of scholarly articles (a companion technical article)
- Sustained acclaim (adoption + contributions over time)

## Why an open-source project, specifically

For NIW evidence, Samar needs to demonstrate impact beyond his employer.
A repository where independent developers and companies adopt the work
provides verifiable, third-party evidence of national-level contribution.
USCIS officers can check GitHub directly. Adoption by named companies in
a "Used by" README section is concrete. Merged PRs from independent
developers are third-party validation.

Stars are a vanity metric; the things that matter for immigration
evidence are:
- Adoption by named organizations (logos in README)
- Sustained download counts (PyPI weekly downloads)
- External contributors with merged PRs
- Citations in industry articles, talks, or papers
- Mentions or use by other major projects

The companion article (separate work, written for Medium / company blog /
trade publications) links to this repo, and the repo links back. Together
they form one piece of evidence: "Samar architected this pattern, wrote
about it publicly, and others adopted it."

## What makes this project NIW-quality (not just a hobby project)

There are existing tutorials for OpenAI Realtime + Twilio. There are toy
demos. There is no clean, production-grade, open-source reference for:

1. **Multi-tenant voice agent infrastructure** with proper config
   isolation, encrypted secrets, and per-tenant agent definition. All
   existing tutorials are single-tenant demos.

2. **A unified tool endpoint pattern** where knowledge bases, MCP
   servers, data tables, custom tools, and workflows all flow through
   a single function-call interface. This is the architectural pattern
   Samar's senior engineer pushed him toward at Kasisto. It is genuinely
   novel for the open-source voice agent space.

3. **First-class MCP server support for voice agents**. MCP is six
   months old and becoming the standard for LLM tool integration. No
   open-source voice agent framework today treats MCP servers as a
   first-class capability.

4. **Production-grade observability and failure handling**. What happens
   when OpenAI Realtime is down? What happens when a tool call fails?
   What happens on call interruption mid-sentence? Tutorials don't cover
   this. Production systems must.

5. **Pluggable everything**: pluggable LLM provider (via OpenAI Agents
   SDK + LiteLLM extension), pluggable knowledge source, pluggable
   telephony layer (Twilio first, SIP/Jambonz later), pluggable observ-
   ability backend.

These five gaps are the project's contribution. Every architectural
decision should serve at least one of them.

## How to evaluate trade-offs

When you (Claude Code) face a design or implementation decision, ask in
this order:

1. **Does this choice support adoption by independent developers?**
   If the answer is no — if it adds friction, requires obscure auth, or
   couples to Samar's specific environment — pick the more standard
   alternative even if it's slightly less elegant.

2. **Is this layer pluggable?** Components people might want to swap
   (LLM provider, telephony, knowledge source, observability) must be
   behind clean interfaces. Components that aren't swappable (the
   unified tool endpoint, multi-tenant config) can be more opinionated.

3. **Is this code review-ready?** Assume a senior engineer at a fintech
   will read this on a Monday morning before deciding whether to
   evaluate it for production use. Variable names, error handling,
   logging, and tests should pass that bar. No shortcuts that would
   embarrass Samar in an interview.

4. **Does this advance one of the five contribution gaps?** If a
   feature doesn't connect to multi-tenancy, the unified tool endpoint,
   MCP support, observability/reliability, or pluggability, it's
   probably out of scope for v0.

When in doubt: **prefer boring, standard, well-documented choices** over
clever ones. This project's value is the architecture, not the
individual technology picks.

## Tech stack — finalized

- **Language**: Python 3.11+. Not negotiable. Author works in Python;
  ecosystem benefits; faster shipping.
- **Agent framework**: OpenAI Agents SDK (`openai-agents`). Provider-
  agnostic via LiteLLM extension. First-party Twilio realtime adapter.
  Built-in handoffs, guardrails, sessions, tracing.
- **Web framework**: FastAPI. Author's daily driver; handles WebSockets
  cleanly; modern async.
- **Telephony (v0)**: Twilio Media Streams via the SDK's
  `TwilioRealtimeTransportLayer`. SIP and Jambonz are post-v0.
- **LLM (v0)**: OpenAI Realtime API (`gpt-realtime`). Pluggable for
  non-realtime fallback paths via LiteLLM.
- **Storage**: PostgreSQL for tenant config; Redis for session state.
  Both via env-configured connection strings, with a SQLite/in-memory
  fallback for the quickstart.
- **Secrets**: encrypted-at-rest in Postgres using Fernet; runtime
  decryption only.
- **Tests**: pytest. Aim for 80%+ coverage on core logic.
- **Deployment**: Docker + docker-compose for local. Kubernetes Helm
  chart as a follow-on, not v0.
- **License**: MIT. Maximum adoption surface.

## Tech stack — explicitly excluded

- **TypeScript**: only if a UI component is added later, and only for
  that UI. Core stays Python.
- **LangChain / LangGraph**: too heavy, opinionated abstractions that
  fight with OpenAI Agents SDK.
- **Claude Agent SDK**: wrong shape (it's Claude Code as a library —
  built for OS-level agents, not real-time voice). Author also doesn't
  have a Claude API key, only a Max plan, which would create auth
  friction for users.
- **GPL or AGPL licenses**: limits adoption.

## Naming

Project name: **`oratium`**. Latin-derived, evocative of oratory and
speech, with no close real-word neighbors (verified clean on PyPI
similarity check). Faintly reminiscent of "auditorium" — a place where
speech happens. Distinctive, Google-able, and brandable beyond pure
voice as the project's scope expands toward conversational AI more
broadly. PyPI name reserved as empty placeholder package; the GitHub
repository lives at `github.com/samarbatra23/oratium`.

## What "done" looks like for v0

The v0 MVP scope document defines the technical bar. From the
immigration-evidence perspective, v0 is "done" when:

1. A developer with no prior context can clone the repo, follow the
   quickstart, and have a working multi-tenant voice agent answering
   a Twilio number within 30 minutes.
2. The README clearly explains the architecture, the five contribution
   gaps, and how to extend each pluggable layer.
3. Test coverage is 80%+.
4. The companion technical article is drafted and ready to publish.
5. The repo is public and announced (Hacker News Show HN, r/MachineLearning,
   r/voicetech, voice AI Discords).

Post-v0 milestones (months 2–6) are tracked in MVP_SCOPE.md.

## What you (Claude Code) have access to

You have access to Samar's Kasisto code via his local machine. **Do not
copy Kasisto code.** Kasisto IP clearance is for *publishing reference
patterns*, not for *copying proprietary code*. When you need to know how
something is done at Kasisto:

- Read the relevant Kasisto code for context only
- Reimplement from scratch in this project, with cleaner abstractions
  appropriate to an open-source library
- Never include Kasisto-specific identifiers, client names, internal
  service names, or proprietary configuration values
- The three Duncan Solutions clients (MassDOT, NJSP, Boston DOT),
  Meriwest Credit Union, Kasisto's "Kaigentic" platform name, and
  Kasisto's internal service names (NexDial, Router, etc.) must not
  appear anywhere in this project

Generic patterns (multi-tenancy, function-call dispatch, encrypted
config, Redis session state) are fair game. Kasisto-specific
implementations are not.

## Companion deliverables (separate from this project)

These are tracked outside this repo but inform what the repo should
emphasize:

1. **Technical article** (Medium / personal blog / dev.to, then trade
   publication): "Beyond pipelines: building a real-time speech-to-
   speech voice agent for regulated banking." Links to repo.
2. **Conference talks** submitted: Voice & AI, Project Voice,
   Money 20/20, FinovateFall, AWS re:Invent breakout, NYC AI meetup,
   NYC Fintech meetup.
3. **Jambonz contribution**: substantial PR to the upstream Jambonz
   project. Separate evidence stream.
4. **Updated resume**: already complete, reflects the past 15 weeks.
5. **Manifest Law engagement**: free consultation booked, then formal
   engagement after profile is built.
6. **Recommender list**: identify 15 candidates, reach out to 8,
   secure 5–6 letters. The repo's adoption helps recommender outreach
   ("I came across your work on X, here's mine").

The repo is the centerpiece, but it's one piece of a six-piece evidence
package.

## What success looks like in 6 months

- Repo: 500+ stars, 2–3 named companies/projects in "Used by", 10–20
  external contributors with merged PRs, 100+ weekly PyPI downloads
  sustained, 1–2 industry article mentions.
- Article: published on Medium and either company blog or trade pub,
  10K+ views, cited in at least one other writeup.
- Talks: 2–3 accepted, at least one with recording publicly available.
- Jambonz PR: merged, listed in release notes.
- Recommenders: 5–6 letters drafted.
- Manifest Law: petition drafted, ready to file with premium processing.

If 60% of those targets are hit, the NIW case is strong. Even at 30%,
it's a credible filing.

## Final note for Claude Code

When you're working on this project, the right mental model is:
"I am building a reference implementation that a senior engineer at a
mid-sized fintech might evaluate for production use, and that an
immigration officer might check the GitHub page of." Both audiences
care about clarity, professionalism, and evidence of genuine adoption.
Optimize for both.

If a decision feels like it's optimizing for one audience at the cost
of the other (e.g., fancy architecture that no one will adopt, or
shallow adoption-bait without real depth), step back and find the
choice that serves both.
