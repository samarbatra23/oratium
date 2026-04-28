"""Single-tenant oratium quickstart.

Run with::

    export OPENAI_API_KEY=sk-...
    uvicorn examples.quickstart.main:app --port 8000

Then expose the server publicly (e.g. ``ngrok http 8000``) and point your
Twilio number's voice webhook at ``https://<your-host>/incoming-call``.
"""

from __future__ import annotations

import oratium

agent = oratium.Agent(
    name="hello-world",
    instructions=(
        "You are a friendly assistant on a phone call. Greet the caller warmly,"
        " keep responses concise, and speak conversationally."
    ),
    voice="alloy",
)

app = oratium.OratiumApp(agent=agent)
