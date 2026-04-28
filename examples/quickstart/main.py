"""Single-tenant oratium quickstart.

Run with::

    export OPENAI_API_KEY=sk-...
    uvicorn examples.quickstart.main:app --port 8000

Then expose the server publicly (e.g. ``ngrok http 8000``) and point your
Twilio number's voice webhook at ``https://<your-host>/incoming-call``.
"""

from __future__ import annotations

import logging

import oratium

# Make oratium's INFO-level logs visible in the terminal. This is the user
# application's responsibility, not the library's; oratium emits log records
# but doesn't configure handlers. Phase 5 adds an opt-in structured-logging
# helper that you can use instead of this basicConfig call.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

agent = oratium.Agent(
    name="hello-world",
    instructions=(
        "You are a friendly assistant on a phone call. The call has just"
        " connected. Open with a brief, warm greeting (one sentence) and ask"
        " how you can help. Keep all subsequent responses concise and"
        " conversational, since this is a phone call."
    ),
    voice="alloy",
    # Pinned to a known-good Realtime model ID for the quickstart. Bump as
    # OpenAI ships GA versions.
    model="gpt-4o-realtime-preview-2024-12-17",
)

app = oratium.OratiumApp(agent=agent)
