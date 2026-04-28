"""High-level :class:`Agent` definition wrapping :class:`agents.realtime.RealtimeAgent`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from agents.realtime import RealtimeAgent
from agents.realtime.model import RealtimeModelConfig

from oratium.tools.unified import UnifiedTools

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
        Either a list of ``@function_tool``-decorated callables (Phase 1
        backward compat) or a :class:`oratium.UnifiedTools` instance
        (Phase 4) that bundles functions, knowledge sources, data tables,
        and MCP servers.
    model:
        Realtime model identifier passed to the runtime.
    """

    name: str
    instructions: str | None = None
    voice: str = DEFAULT_VOICE
    tools: list[Any] | UnifiedTools = field(default_factory=list)
    model: str = DEFAULT_MODEL

    def _unified(self) -> UnifiedTools | None:
        """Return the UnifiedTools view of this agent's tools, or None if empty."""
        if isinstance(self.tools, UnifiedTools):
            return self.tools
        if self.tools:
            return UnifiedTools(functions=list(self.tools))
        return None

    def to_realtime_agent(self, *, api_key: str | None = None) -> RealtimeAgent[Any]:
        """Build the underlying SDK :class:`RealtimeAgent`.

        ``api_key`` is required only if this agent has knowledge sources
        configured (knowledge embedding needs an OpenAI key).
        """
        unified = self._unified()
        sdk_tools: list[Any] = []
        sdk_mcp_servers: list[Any] = []
        if unified is not None:
            sdk_tools = unified.to_realtime_tools(api_key=api_key)
            sdk_mcp_servers = unified.to_mcp_servers()
        return RealtimeAgent(
            name=self.name,
            instructions=self.instructions,
            tools=sdk_tools,
            mcp_servers=sdk_mcp_servers,
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
