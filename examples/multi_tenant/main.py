"""Multi-tenant oratium quickstart — two phone numbers, two distinct agents.

Run with::

    export OPENAI_API_KEY=sk-...
    uvicorn examples.multi_tenant.main:app --port 8421

Then point TWO Twilio numbers' voice webhooks at
``https://<your-host>/incoming-call``. Edit ``tenants.yaml`` to use your
actual numbers. oratium routes each inbound call to the right agent based
on the called number (Twilio's ``To`` parameter).
"""

from __future__ import annotations

import logging
from pathlib import Path

import oratium

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

tenants = oratium.YAMLTenantStore(Path(__file__).parent / "tenants.yaml")

app = oratium.OratiumApp(tenants=tenants)
