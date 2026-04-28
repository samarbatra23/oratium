"""Twilio Media Streams transport for the OpenAI Realtime API.

Bridges a Twilio Media Streams websocket to an OpenAI Realtime session.
Owns the websocket after handshake, pumps inbound audio into
:meth:`RealtimeSession.send_audio`, and forwards outbound
:class:`RealtimeAudio` and :class:`RealtimeAudioInterrupted` events back to
Twilio. Twilio mark events are reflected into the session's
:class:`RealtimePlaybackTracker` so interruption math stays accurate.

This class exists because the OpenAI Agents Python SDK does not yet ship an
equivalent to the JS ``@openai/agents-extensions`` ``TwilioRealtimeTransportLayer``.
See ``docs/architecture.md`` decisions 0001 and 0002 for the design and the
upgrade path when the upstream SDK ships its own adapter.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
from typing import Any

from agents.realtime import (
    RealtimePlaybackTracker,
    RealtimeSession,
    RealtimeSessionEvent,
)
from agents.realtime.events import RealtimeAudio, RealtimeAudioInterrupted
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


# Twilio Media Streams uses G.711 μ-law at 8 kHz.
DEFAULT_SAMPLE_RATE = 8000
DEFAULT_CHUNK_LENGTH_S = 0.05  # 50 ms
DEFAULT_STARTUP_BUFFER_CHUNKS = 3


class TwilioMediaStreamTransport:
    """Owns a Twilio Media Streams websocket and pumps audio to/from a session.

    Lifecycle::

        transport = TwilioMediaStreamTransport(websocket, session, tracker)
        await transport.run()

    ``run()`` returns when Twilio disconnects (or sends a ``stop`` event).
    Construction does not start the loops; ``run()`` accepts the websocket
    and then runs three concurrent loops via :class:`asyncio.TaskGroup`:

    * Reading messages from Twilio and feeding audio to the session
    * Reading events from the session and forwarding audio to Twilio
    * Periodically flushing the inbound audio buffer to keep latency low

    Parameters
    ----------
    websocket:
        The not-yet-accepted Twilio Media Streams websocket. The transport
        calls ``accept()`` itself in ``run``.
    session:
        A :class:`agents.realtime.RealtimeSession` the caller has already
        configured. The session's ``input_audio_format`` and
        ``output_audio_format`` should be ``"g711_ulaw"`` so audio passes
        through unchanged.
    playback_tracker:
        Tracker passed in the session's ``model_config``. Twilio mark events
        feed it so OpenAI's interruption math reflects what the caller has
        actually heard.
    sample_rate:
        Twilio sample rate in Hz (μ-law is 8000).
    chunk_length_s:
        Inbound buffer chunk length in seconds. Each buffer flush sends a
        block of this duration to the session.
    startup_buffer_chunks:
        Number of chunks to accumulate before the first send. Smooths the
        initial connection at the cost of a small added delay. Set to ``0``
        to disable.
    """

    def __init__(
        self,
        websocket: WebSocket,
        session: RealtimeSession,
        playback_tracker: RealtimePlaybackTracker,
        *,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        chunk_length_s: float = DEFAULT_CHUNK_LENGTH_S,
        startup_buffer_chunks: int = DEFAULT_STARTUP_BUFFER_CHUNKS,
    ) -> None:
        self._websocket = websocket
        self._session = session
        self._playback_tracker = playback_tracker
        self._sample_rate = sample_rate
        self._chunk_length_s = chunk_length_s
        self._buffer_size_bytes = int(sample_rate * chunk_length_s)
        self._startup_buffer_chunks = max(0, startup_buffer_chunks)

        self._stream_sid: str | None = None
        self._audio_buffer = bytearray()
        self._last_buffer_send_time = time.monotonic()

        self._mark_counter = 0
        self._mark_data: dict[str, tuple[str, int, int]] = {}

        self._startup_buffer = bytearray()
        self._startup_warmed = self._startup_buffer_chunks == 0

    @property
    def stream_sid(self) -> str | None:
        """Twilio's stream SID, populated when the ``start`` event arrives."""
        return self._stream_sid

    async def run(self) -> None:
        """Run the transport until the Twilio websocket disconnects."""
        await self._websocket.accept()
        logger.info("Twilio media stream websocket accepted")

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._twilio_message_loop(), name="twilio_messages")
                tg.create_task(self._realtime_session_loop(), name="realtime_session")
                tg.create_task(self._buffer_flush_loop(), name="buffer_flush")
        except* WebSocketDisconnect:
            logger.info("Twilio websocket disconnected; transport stopped")
        # Other ExceptionGroups propagate to the caller.

    async def _twilio_message_loop(self) -> None:
        while True:
            raw = await self._websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Could not parse Twilio message as JSON: %r", raw)
                continue
            await self._handle_twilio_message(message)

    async def _handle_twilio_message(self, message: dict[str, Any]) -> None:
        event = message.get("event")
        if event == "media":
            await self._handle_media_event(message)
        elif event == "mark":
            self._handle_mark_event(message)
        elif event == "start":
            start = message.get("start") or {}
            self._stream_sid = start.get("streamSid")
            logger.info("Twilio media stream started: streamSid=%s", self._stream_sid)
        elif event == "stop":
            logger.info("Twilio media stream stopped by remote")
            raise WebSocketDisconnect(code=1000)
        elif event == "connected":
            logger.debug("Twilio media stream connected")
        else:
            logger.debug("Unhandled Twilio event type: %s", event)

    async def _handle_media_event(self, message: dict[str, Any]) -> None:
        media = message.get("media") or {}
        payload = media.get("payload", "")
        if not payload:
            return
        try:
            ulaw_bytes = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            logger.warning("Could not base64-decode Twilio media payload")
            return
        self._audio_buffer.extend(ulaw_bytes)
        if len(self._audio_buffer) >= self._buffer_size_bytes:
            await self._flush_audio_buffer()

    def _handle_mark_event(self, message: dict[str, Any]) -> None:
        mark = message.get("mark") or {}
        mark_id = mark.get("name", "")
        if not mark_id or mark_id not in self._mark_data:
            return
        item_id, content_index, byte_count = self._mark_data.pop(mark_id)
        self._playback_tracker.on_play_bytes(item_id, content_index, b"\x00" * byte_count)
        logger.debug(
            "Playback tracker updated: item=%s content_index=%d bytes=%d",
            item_id,
            content_index,
            byte_count,
        )

    async def _flush_audio_buffer(self) -> None:
        if not self._audio_buffer:
            return
        chunk = bytes(self._audio_buffer)
        self._audio_buffer.clear()
        self._last_buffer_send_time = time.monotonic()

        if not self._startup_warmed:
            self._startup_buffer.extend(chunk)
            target = self._buffer_size_bytes * self._startup_buffer_chunks
            if len(self._startup_buffer) >= target:
                await self._session.send_audio(bytes(self._startup_buffer))
                self._startup_buffer.clear()
                self._startup_warmed = True
            return
        await self._session.send_audio(chunk)

    async def _buffer_flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._chunk_length_s)
            now = time.monotonic()
            if (
                self._audio_buffer
                and (now - self._last_buffer_send_time) > self._chunk_length_s * 2
            ):
                await self._flush_audio_buffer()

    async def _realtime_session_loop(self) -> None:
        async for event in self._session:
            await self._handle_realtime_event(event)

    async def _handle_realtime_event(self, event: RealtimeSessionEvent) -> None:
        if isinstance(event, RealtimeAudio):
            await self._send_audio_to_twilio(event)
        elif isinstance(event, RealtimeAudioInterrupted):
            logger.info("Realtime audio interrupted; clearing Twilio buffer")
            await self._websocket.send_text(
                json.dumps({"event": "clear", "streamSid": self._stream_sid})
            )

    async def _send_audio_to_twilio(self, event: RealtimeAudio) -> None:
        payload = base64.b64encode(event.audio.data).decode("ascii")
        await self._websocket.send_text(
            json.dumps(
                {
                    "event": "media",
                    "streamSid": self._stream_sid,
                    "media": {"payload": payload},
                }
            )
        )
        self._mark_counter += 1
        mark_id = str(self._mark_counter)
        self._mark_data[mark_id] = (
            event.audio.item_id,
            event.audio.content_index,
            len(event.audio.data),
        )
        await self._websocket.send_text(
            json.dumps(
                {
                    "event": "mark",
                    "streamSid": self._stream_sid,
                    "mark": {"name": mark_id},
                }
            )
        )
