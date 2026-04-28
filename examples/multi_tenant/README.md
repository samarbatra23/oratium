# oratium multi-tenant example

Two Twilio numbers, two distinct agents, one oratium process. Calls route
based on the called number; the support line answers in `alloy`, the sales
line answers in `verse`. Adding a third tenant is a YAML edit.

## Prerequisites

Same as the [single-tenant quickstart](../quickstart/README.md):

- Python 3.11+
- `OPENAI_API_KEY` with Realtime API access
- A Twilio account, with **two** phone numbers in this example
- A tunnel (ngrok / Cloudflare Tunnel / similar)

## Steps

1. **Edit `tenants.yaml`.** Replace the placeholder `twilio_number` values
   with your two real Twilio numbers in E.164 format (`+15555550100` style).
   Customize the agent `name`, `instructions`, and `voice` per tenant.

2. **Install oratium and start the server.**

   ```bash
   pip install oratium
   export OPENAI_API_KEY=sk-...
   uvicorn examples.multi_tenant.main:app --port 8421
   ```

3. **Expose it publicly.**

   ```bash
   ngrok http 8421
   ```

4. **Point both Twilio numbers at oratium.** In the Twilio console, on
   each number's Voice & Fax settings, set "A call comes in" to **Webhook**
   with URL `https://<id>.ngrok-free.app/incoming-call` and method **POST**.
   The same webhook URL serves both numbers — oratium picks the right
   tenant from Twilio's `To` parameter.

5. **Call each number.** Each should answer in its configured voice with
   its own greeting style.

## How routing works

When Twilio POSTs to `/incoming-call`, the form body includes a `To`
field containing the called number. oratium:

1. Looks up the tenant by `To` number in the configured `TenantStore`
   (`YAMLTenantStore` here, but `SQLiteTenantStore` and
   `PostgresTenantStore` are drop-in replacements).
2. Returns TwiML that bridges the call to
   `wss://<host>/media-stream/<tenant_id>`.
3. The websocket handler reads the tenant id from the URL path,
   refetches the tenant, and builds the runtime agent for this call.

(The path segment, not a query string — Twilio's `<Stream>` URL handling
strips query strings on the actual websocket connection. Decision 0005
in `docs/architecture.md` has the details.)

Calls to numbers not in the YAML get a polite "this number is not
configured" message instead of fast-busy.

## Switching to SQLite or Postgres

Same code, different store:

```python
# SQLite (single-node):
tenants = oratium.SQLiteTenantStore("./oratium.sqlite3")
await tenants.initialize()  # creates the table on first run

# Postgres (multi-node):
tenants = oratium.PostgresTenantStore("postgresql://user:pass@host/db")
# Run migrations once: `alembic upgrade head` from the oratium package
```

Then `oratium.OratiumApp(tenants=tenants)` is unchanged. See decision
0005 in `docs/architecture.md` for when each backend is the right pick.
