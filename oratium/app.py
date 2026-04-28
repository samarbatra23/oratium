"""FastAPI app factory wiring Twilio webhooks and Media Streams to an oratium :class:`Agent`."""

from __future__ import annotations

import logging
import os

from agents.realtime import RealtimePlaybackTracker, RealtimeRunner
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import PlainTextResponse
from starlette.types import Receive, Scope, Send

from oratium.agent import Agent
from oratium.transport.twilio import TwilioMediaStreamTransport

logger = logging.getLogger(__name__)


# TwiML response for an inbound Twilio call: bridge straight to the media-stream
# websocket. Host is filled in at request time so the same code works behind
# any tunnel (ngrok, Cloudflare, etc.) without redeployment.
_TWIML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}{path}" />
    </Connect>
</Response>"""


class OratiumApp:
    """ASGI application wiring an :class:`oratium.Agent` to Twilio webhooks.

    Single-tenant for v0 Phase 1. Phase 2 introduces tenant resolution based
    on the called number, replacing the single ``agent`` argument.

    The instance is itself an ASGI app — use it directly with uvicorn::

        agent = oratium.Agent(name="hello", instructions="Greet the caller.")
        app = oratium.OratiumApp(agent=agent)
        # Run with: uvicorn module:app --port 8000

    Parameters
    ----------
    agent:
        The agent that answers inbound calls.
    api_key:
        OpenAI API key. Defaults to ``$OPENAI_API_KEY``.
    incoming_call_path:
        HTTP path Twilio hits for an inbound call (default ``/incoming-call``).
    media_stream_path:
        WebSocket path Twilio Media Streams connects to (default
        ``/media-stream``).
    """

    def __init__(
        self,
        agent: Agent,
        *,
        api_key: str | None = None,
        incoming_call_path: str = "/incoming-call",
        media_stream_path: str = "/media-stream",
    ) -> None:
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError("OPENAI_API_KEY is not set. Pass api_key=... or set the env var.")
        self._agent = agent
        self._api_key: str = resolved_key
        self._incoming_call_path = incoming_call_path
        self._media_stream_path = media_stream_path
        self._fastapi = self._build_fastapi()

    @property
    def fastapi(self) -> FastAPI:
        """The underlying FastAPI app, exposed for advanced customization."""
        return self._fastapi

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._fastapi(scope, receive, send)

    def _build_fastapi(self) -> FastAPI:
        app = FastAPI()

        @app.get("/")
        async def root() -> dict[str, str]:
            return {"status": "ok", "service": "oratium"}

        @app.api_route(self._incoming_call_path, methods=["GET", "POST"])
        async def incoming_call(request: Request) -> PlainTextResponse:
            host = request.headers.get("host", "")
            twiml = _TWIML_TEMPLATE.format(host=host, path=self._media_stream_path)
            return PlainTextResponse(content=twiml, media_type="text/xml")

        @app.websocket(self._media_stream_path)
        async def media_stream(websocket: WebSocket) -> None:  # pragma: no cover
            # Orchestrates SDK calls (RealtimeRunner, RealtimeSession.enter)
            # plus the transport. Unit-testing this would mostly exercise the
            # SDK; integration coverage comes from examples/quickstart.
            playback_tracker = RealtimePlaybackTracker()
            runner = RealtimeRunner(self._agent.to_realtime_agent())
            session = await runner.run(
                model_config=self._agent.model_config(
                    api_key=self._api_key,
                    playback_tracker=playback_tracker,
                ),
            )
            await session.enter()
            transport = TwilioMediaStreamTransport(
                websocket=websocket,
                session=session,
                playback_tracker=playback_tracker,
            )
            await transport.run()

        return app
