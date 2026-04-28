"""FastAPI app factory wiring Twilio webhooks and Media Streams to oratium agents."""

from __future__ import annotations

import logging
import os

from agents.realtime import RealtimePlaybackTracker, RealtimeRunner
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import PlainTextResponse
from starlette.types import Receive, Scope, Send

from oratium.agent import Agent
from oratium.storage.base import TenantStore
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


# TwiML returned when a multi-tenant deployment receives a call to a number
# that has no configured tenant. We play a brief message rather than 404'ing
# the webhook so the caller hears something instead of fast-busy.
_NO_TENANT_TWIML = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>This number is not currently configured. Please contact support.</Say>
    <Hangup/>
</Response>"""


class OratiumApp:
    """ASGI application wiring oratium agents to Twilio webhooks.

    Two modes, mutually exclusive:

    * **Single-tenant** (Phase 1): pass ``agent=Agent(...)``. Every call
      routes to the same agent.
    * **Multi-tenant** (Phase 2): pass ``tenants=TenantStore``. The
      webhook resolves a tenant from the called Twilio number and the
      websocket builds the agent dynamically per call.

    The instance is itself an ASGI app — use it directly with uvicorn::

        agent = oratium.Agent(name="hello", instructions="Greet the caller.")
        app = oratium.OratiumApp(agent=agent)
        # Run with: uvicorn module:app --port 8000

    Parameters
    ----------
    agent:
        Single-tenant agent. Mutually exclusive with ``tenants``.
    tenants:
        Multi-tenant store. Mutually exclusive with ``agent``.
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
        agent: Agent | None = None,
        *,
        tenants: TenantStore | None = None,
        api_key: str | None = None,
        incoming_call_path: str = "/incoming-call",
        media_stream_path: str = "/media-stream",
    ) -> None:
        if (agent is None) == (tenants is None):
            raise ValueError("Provide exactly one of agent= or tenants=")

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError("OPENAI_API_KEY is not set. Pass api_key=... or set the env var.")

        self._agent = agent
        self._tenants = tenants
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

            if self._tenants is None:
                twiml = _TWIML_TEMPLATE.format(host=host, path=self._media_stream_path)
                return PlainTextResponse(content=twiml, media_type="text/xml")

            to_number = await _extract_to_number(request)
            if not to_number:
                logger.warning("Inbound call with no 'To' parameter; cannot resolve tenant")
                return PlainTextResponse(content=_NO_TENANT_TWIML, media_type="text/xml")

            tenant = await self._tenants.get_by_twilio_number(to_number)
            if tenant is None:
                logger.warning("No tenant configured for %s", to_number)
                return PlainTextResponse(content=_NO_TENANT_TWIML, media_type="text/xml")

            logger.info("Routing inbound call to %s -> tenant %s", to_number, tenant.id)
            # Tenant id travels as a path segment, not a query string. Twilio's
            # <Stream> URL handling drops query strings on the actual Media
            # Streams websocket connection, so the websocket would arrive
            # without the tenant param. A path segment is unambiguous.
            stream_path = f"{self._media_stream_path}/{tenant.id}"
            twiml = _TWIML_TEMPLATE.format(host=host, path=stream_path)
            return PlainTextResponse(content=twiml, media_type="text/xml")

        if self._tenants is None:

            @app.websocket(self._media_stream_path)
            async def media_stream_single(  # pragma: no cover
                websocket: WebSocket,
            ) -> None:
                await self._run_session(websocket, tenant_id=None)

        else:

            @app.websocket(f"{self._media_stream_path}/{{tenant}}")
            async def media_stream_multi(  # pragma: no cover
                websocket: WebSocket,
                tenant: str,
            ) -> None:
                await self._run_session(websocket, tenant_id=tenant)

        return app

    async def _run_session(  # pragma: no cover
        self,
        websocket: WebSocket,
        tenant_id: str | None,
    ) -> None:
        """Run a full call: resolve agent, build session, drive transport.

        Shared between single-tenant and multi-tenant websocket routes.
        Marked ``no cover`` because the body is mostly orchestration of SDK
        calls; integration coverage comes from ``examples/quickstart`` and
        ``examples/multi_tenant``.
        """
        resolution = await self._resolve_call(websocket, tenant_id)
        if resolution is None:
            return
        agent, api_key = resolution

        playback_tracker = RealtimePlaybackTracker()
        runner = RealtimeRunner(agent.to_realtime_agent())
        session = await runner.run(
            model_config=agent.model_config(
                api_key=api_key,
                playback_tracker=playback_tracker,
            ),
        )
        await session.enter()
        logger.info("Session opened; sending greeting trigger to agent")
        await session.send_message("Hello")
        transport = TwilioMediaStreamTransport(
            websocket=websocket,
            session=session,
            playback_tracker=playback_tracker,
        )
        await transport.run()

    async def _resolve_call(  # pragma: no cover
        self,
        websocket: WebSocket,
        tenant_id: str | None,
    ) -> tuple[Agent, str] | None:
        """Pick the agent and OpenAI API key for this websocket connection.

        Returns ``(agent, api_key)`` or ``None`` if the call should not
        proceed (multi-tenant mode + missing or unknown tenant). The
        per-tenant ``secrets.openai_api_key`` overrides the deployment-wide
        key when present.
        """
        if self._tenants is None:
            assert self._agent is not None  # validated in __init__
            return self._agent, self._api_key

        if tenant_id is None:
            logger.warning("media-stream websocket opened with no tenant param")
            await websocket.close(code=1003, reason="missing tenant")
            return None

        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None:
            logger.warning("media-stream websocket: unknown tenant id %s", tenant_id)
            await websocket.close(code=1003, reason="unknown tenant")
            return None

        return tenant.to_runtime_agent(), tenant.resolve_api_key(self._api_key)


async def _extract_to_number(request: Request) -> str | None:
    """Pull the called Twilio number from a webhook request.

    Twilio sends ``To`` as a form field on POST. GET requests (less common
    but supported by some configurations) put it in the query string.
    """
    if request.method == "POST":
        form = await request.form()
        value = form.get("To")
        if isinstance(value, str) and value:
            return value
    value = request.query_params.get("To")
    return value if value else None
