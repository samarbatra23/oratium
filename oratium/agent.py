"""High-level :class:`Agent` definition wrapping :class:`agents.realtime.RealtimeAgent`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from agents.realtime import RealtimeAgent
from agents.realtime.model import RealtimeModelConfig

DEFAULT_MODEL = "gpt-realtime"
DEFAULT_VOICE = "alloy"


@dataclass(slots=True)
class Agent:
    """A voice agent definition.

    Wraps :class:`agents.realtime.RealtimeAgent` while exposing the small
    surface area oratium publishes. ``voice`` and ``model`` live here even
    though the underlying SDK applies them at session-creation time via
    ``model_config``: adopters expect them on the agent definition.

    Parameters
    ----------
    name:
        Human-readable agent name. Surfaces in logs and traces.
    instructions:
        System prompt for the agent. ``None`` falls back to the SDK default.
    voice:
        OpenAI Realtime voice (e.g. ``"alloy"``, ``"verse"``).
    tools:
        Tools the agent may call. Each must be a function decorated with
        :func:`agents.function_tool` or an SDK ``Tool`` instance.
    model:
        Realtime model identifier passed to the runtime.
    """

    name: str
    instructions: str | None = None
    voice: str = DEFAULT_VOICE
    tools: list[Any] = field(default_factory=list)
    model: str = DEFAULT_MODEL

    def to_realtime_agent(self) -> RealtimeAgent[Any]:
        """Build the underlying SDK :class:`RealtimeAgent`."""
        return RealtimeAgent(
            name=self.name,
            instructions=self.instructions,
            tools=list(self.tools),
        )

    def model_config(
        self,
        *,
        api_key: str,
        playback_tracker: Any | None = None,
    ) -> RealtimeModelConfig:
        """Build the ``model_config`` consumed by :meth:`RealtimeRunner.run`.

        ``playback_tracker`` is typed loosely so this module does not import
        :class:`agents.realtime.RealtimePlaybackTracker` purely for typing;
        in practice callers pass an instance of it.
        """
        config: dict[str, Any] = {
            "api_key": api_key,
            "initial_model_settings": {
                "model_name": self.model,
                "voice": self.voice,
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "turn_detection": {
                    "type": "semantic_vad",
                    "interrupt_response": True,
                    "create_response": True,
                },
            },
        }
        if playback_tracker is not None:
            config["playback_tracker"] = playback_tracker
        return cast(RealtimeModelConfig, config)
