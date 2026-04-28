# oratium quickstart

A single-tenant voice agent answering inbound Twilio calls. Five minutes from
clone to a working phone number, end to end.

## Prerequisites

- Python 3.11+
- An OpenAI API key with [Realtime API][openai-realtime] access
- A [Twilio][twilio] account with a phone number you control
- A tunnel — [ngrok][ngrok], Cloudflare Tunnel, or similar — to expose your
  local server to Twilio

## Steps

1. **Install oratium.**

    ```bash
    pip install oratium
    ```

2. **Set credentials.**

    ```bash
    export OPENAI_API_KEY=sk-...
    ```

3. **Run the server.**

    ```bash
    uvicorn examples.quickstart.main:app --port 8000
    ```

4. **Expose it publicly.**

    ```bash
    ngrok http 8000
    ```

    Note the `https://<id>.ngrok.io` URL.

5. **Point Twilio at oratium.**

    In the Twilio console, on your phone number's Voice & Fax settings, set
    "A call comes in" to **Webhook** with the URL
    `https://<id>.ngrok.io/incoming-call` and HTTP method **POST**.

6. **Call the number.** The agent answers and you can have a conversation.

## What the example does

`main.py` is fifteen lines. It creates an `oratium.Agent` with a name,
instructions, and a voice, wraps it in `oratium.OratiumApp`, and exposes that
as an ASGI app uvicorn can serve.

The `OratiumApp` registers two routes:

- `POST /incoming-call` — Twilio's voice webhook. Returns TwiML that bridges
  the call to a websocket.
- `WebSocket /media-stream` — Twilio Media Streams connection. Audio flows
  through `oratium.transport.twilio.TwilioMediaStreamTransport` to an OpenAI
  Realtime session and back.

## What's next

- Add tools — see the multi-tenant and MCP examples (Phase 2 onward).
- Swap voices — pass `voice="verse"` (or any supported voice) to the Agent.
- Run multi-tenant — the multi-tenant example shows two agents on two numbers.

[openai-realtime]: https://platform.openai.com/docs/guides/realtime
[twilio]: https://www.twilio.com/docs/voice
[ngrok]: https://ngrok.com/
