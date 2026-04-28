from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from agents.realtime import RealtimePlaybackTracker
from agents.realtime.events import (
    RealtimeAudio,
    RealtimeAudioInterrupted,
    RealtimeEventInfo,
)
from agents.realtime.model_events import RealtimeModelAudioEvent
from agents.run_context import RunContextWrapper
from starlette.websockets import WebSocketDisconnect

from oratium.transport.twilio import TwilioMediaStreamTransport

# --- fakes ---


class FakeWebSocket:
    """Minimal stand-in for fastapi.WebSocket."""

    def __init__(self, incoming: list[str] | None = None) -> None:
        self._incoming: list[str] = list(incoming or [])
        self.sent: list[dict[str, Any]] = []
        self.accepted = False
        self.disconnect_after_drain = True

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if self._incoming:
            return self._incoming.pop(0)
        if self.disconnect_after_drain:
            raise WebSocketDisconnect(code=1000)
        await asyncio.Event().wait()  # block forever
        raise AssertionError("unreachable")

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    def queue(self, message: dict[str, Any]) -> None:
        self._incoming.append(json.dumps(message))


class FakeSession:
    """Minimal stand-in for agents.realtime.RealtimeSession."""

    def __init__(self, events: list[Any] | None = None) -> None:
        self._events = list(events or [])
        self.audio_sent: list[bytes] = []

    async def send_audio(self, audio: bytes) -> None:
        self.audio_sent.append(audio)

    def __aiter__(self) -> AsyncIterator[Any]:
        async def gen() -> AsyncIterator[Any]:
            for event in self._events:
                yield event
                await asyncio.sleep(0)
            # Block forever after exhausting events; the TaskGroup cancels us
            # when the Twilio loop ends.
            await asyncio.Event().wait()

        return gen()


def _audio_event(data: bytes, item_id: str = "item-1", content_index: int = 0) -> RealtimeAudio:
    info = RealtimeEventInfo(context=RunContextWrapper(context=None))
    audio_event = RealtimeModelAudioEvent(
        data=data,
        response_id="resp-1",
        item_id=item_id,
        content_index=content_index,
    )
    return RealtimeAudio(
        audio=audio_event,
        item_id=item_id,
        content_index=content_index,
        info=info,
    )


def _audio_interrupted(item_id: str = "item-1", content_index: int = 0) -> RealtimeAudioInterrupted:
    info = RealtimeEventInfo(context=RunContextWrapper(context=None))
    return RealtimeAudioInterrupted(info=info, item_id=item_id, content_index=content_index)


def _build_transport(
    *,
    incoming: list[dict[str, Any]] | None = None,
    session_events: list[Any] | None = None,
    startup_buffer_chunks: int = 0,
) -> tuple[TwilioMediaStreamTransport, FakeWebSocket, FakeSession, RealtimePlaybackTracker]:
    ws = FakeWebSocket()
    if incoming:
        for msg in incoming:
            ws.queue(msg)
    session = FakeSession(events=session_events)
    tracker = RealtimePlaybackTracker()
    transport = TwilioMediaStreamTransport(
        websocket=ws,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
        playback_tracker=tracker,
        startup_buffer_chunks=startup_buffer_chunks,
    )
    return transport, ws, session, tracker


# --- handler-level unit tests ---


async def test_start_event_sets_stream_sid() -> None:
    transport, _, _, _ = _build_transport()
    await transport._handle_twilio_message({"event": "start", "start": {"streamSid": "MZ123"}})
    assert transport.stream_sid == "MZ123"


async def test_connected_event_does_nothing_observable() -> None:
    transport, _, session, _ = _build_transport()
    await transport._handle_twilio_message({"event": "connected"})
    assert transport.stream_sid is None
    assert session.audio_sent == []


async def test_unknown_event_is_ignored() -> None:
    transport, _, session, _ = _build_transport()
    await transport._handle_twilio_message({"event": "weird-event"})
    assert session.audio_sent == []


async def test_media_event_buffers_until_full() -> None:
    transport, _, session, _ = _build_transport()
    payload = base64.b64encode(b"\xff" * 100).decode("ascii")
    await transport._handle_twilio_message({"event": "media", "media": {"payload": payload}})
    # 100 bytes < 400-byte threshold; not flushed.
    assert session.audio_sent == []


async def test_media_event_flushes_when_full() -> None:
    transport, _, session, _ = _build_transport()
    payload = base64.b64encode(b"\xff" * 400).decode("ascii")
    await transport._handle_twilio_message({"event": "media", "media": {"payload": payload}})
    assert session.audio_sent == [b"\xff" * 400]


async def test_startup_buffer_holds_first_chunks_then_releases_combined() -> None:
    transport, _, session, _ = _build_transport(startup_buffer_chunks=3)
    payload = base64.b64encode(b"\x55" * 400).decode("ascii")
    for _ in range(3):
        await transport._handle_twilio_message({"event": "media", "media": {"payload": payload}})
    # 3 chunks combined into one warm-up send (3 * 400 = 1200 bytes).
    assert session.audio_sent == [b"\x55" * 1200]
    # Subsequent chunks send individually.
    await transport._handle_twilio_message({"event": "media", "media": {"payload": payload}})
    assert session.audio_sent == [b"\x55" * 1200, b"\x55" * 400]


async def test_startup_buffer_disabled_when_zero_chunks() -> None:
    transport, _, session, _ = _build_transport(startup_buffer_chunks=0)
    payload = base64.b64encode(b"\xaa" * 400).decode("ascii")
    await transport._handle_twilio_message({"event": "media", "media": {"payload": payload}})
    assert session.audio_sent == [b"\xaa" * 400]


async def test_unparseable_media_payload_is_skipped() -> None:
    transport, _, session, _ = _build_transport()
    await transport._handle_twilio_message(
        {"event": "media", "media": {"payload": "!!!not-base64"}}
    )
    assert session.audio_sent == []


async def test_empty_media_payload_is_ignored() -> None:
    transport, _, session, _ = _build_transport()
    await transport._handle_twilio_message({"event": "media", "media": {"payload": ""}})
    assert session.audio_sent == []


async def test_media_event_without_media_field() -> None:
    transport, _, session, _ = _build_transport()
    await transport._handle_twilio_message({"event": "media"})
    assert session.audio_sent == []


async def test_handle_realtime_audio_emits_media_then_mark() -> None:
    transport, ws, _, _ = _build_transport()
    transport._stream_sid = "MZ-x"

    await transport._handle_realtime_event(_audio_event(data=b"\x00\x01\x02"))

    assert len(ws.sent) == 2
    media, mark = ws.sent
    assert media["event"] == "media"
    assert media["streamSid"] == "MZ-x"
    assert base64.b64decode(media["media"]["payload"]) == b"\x00\x01\x02"
    assert mark["event"] == "mark"
    assert mark["mark"]["name"] == "1"
    assert mark["streamSid"] == "MZ-x"


async def test_handle_realtime_audio_increments_mark_counter() -> None:
    transport, ws, _, _ = _build_transport()
    transport._stream_sid = "MZ-x"

    await transport._handle_realtime_event(_audio_event(data=b"\x00"))
    await transport._handle_realtime_event(_audio_event(data=b"\x01"))

    marks = [m for m in ws.sent if m.get("event") == "mark"]
    assert [m["mark"]["name"] for m in marks] == ["1", "2"]


async def test_handle_realtime_audio_interrupted_emits_clear() -> None:
    transport, ws, _, _ = _build_transport()
    transport._stream_sid = "MZ-x"

    await transport._handle_realtime_event(_audio_interrupted())

    assert ws.sent == [{"event": "clear", "streamSid": "MZ-x"}]


async def test_mark_event_dispatches_to_playback_tracker() -> None:
    transport, _, _, tracker = _build_transport()
    transport._stream_sid = "MZ-x"
    await transport._handle_realtime_event(
        _audio_event(data=b"\x10" * 50, item_id="item-7", content_index=3)
    )

    calls: list[tuple[str, int, int]] = []
    real = tracker.on_play_bytes

    def stub(item_id: str, content_index: int, audio: bytes) -> None:
        calls.append((item_id, content_index, len(audio)))
        real(item_id, content_index, audio)

    tracker.on_play_bytes = stub  # type: ignore[method-assign]

    await transport._handle_twilio_message({"event": "mark", "mark": {"name": "1"}})

    assert calls == [("item-7", 3, 50)]


async def test_mark_event_unknown_id_is_silently_ignored() -> None:
    transport, _, _, tracker = _build_transport()
    calls: list[Any] = []
    tracker.on_play_bytes = lambda *args, **_kwargs: calls.append(args)  # type: ignore[method-assign]

    await transport._handle_twilio_message({"event": "mark", "mark": {"name": "999"}})

    assert calls == []


async def test_mark_event_with_no_mark_name() -> None:
    transport, _, _, tracker = _build_transport()
    calls: list[Any] = []
    tracker.on_play_bytes = lambda *args, **_kwargs: calls.append(args)  # type: ignore[method-assign]

    await transport._handle_twilio_message({"event": "mark", "mark": {}})

    assert calls == []


# --- lifecycle tests via run() ---


async def test_run_accepts_websocket_and_returns_on_disconnect() -> None:
    transport, ws, _, _ = _build_transport(incoming=[])  # disconnects on first receive
    await transport.run()
    assert ws.accepted


async def test_run_returns_when_twilio_sends_stop() -> None:
    transport, ws, _, _ = _build_transport(incoming=[{"event": "stop"}])
    ws.disconnect_after_drain = False
    await transport.run()
    # Reaches here without raising.


async def test_run_propagates_unparseable_outer_message() -> None:
    # Verifies the top-level loop is robust to garbage; the loop continues
    # and we end via WebSocketDisconnect on drain.
    ws = FakeWebSocket(incoming=["not-json{{{"])
    session = FakeSession()
    tracker = RealtimePlaybackTracker()
    transport = TwilioMediaStreamTransport(
        websocket=ws,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
        playback_tracker=tracker,
        startup_buffer_chunks=0,
    )
    await transport.run()
    assert session.audio_sent == []


@pytest.mark.parametrize("startup_chunks", [0, 1, 5])
async def test_startup_buffer_chunks_parameter_normalises(startup_chunks: int) -> None:
    transport, _, _, _ = _build_transport(startup_buffer_chunks=startup_chunks)
    assert transport._startup_buffer_chunks == startup_chunks
    # Negative values are clamped to 0.
    transport_neg, _, _, _ = _build_transport(startup_buffer_chunks=-3)
    assert transport_neg._startup_buffer_chunks == 0
