from agents import function_tool
from agents.realtime import RealtimeAgent, RealtimePlaybackTracker

from oratium.agent import DEFAULT_MODEL, DEFAULT_VOICE, Agent
from oratium.tools.data_tables import DataTable
from oratium.tools.unified import UnifiedTools


def test_minimal_construction() -> None:
    agent = Agent(name="hello")
    assert agent.name == "hello"
    assert agent.instructions is None
    assert agent.voice == DEFAULT_VOICE
    assert agent.model == DEFAULT_MODEL
    assert agent.tools == []


def test_full_construction() -> None:
    def fake_tool() -> str:
        return "tool"

    agent = Agent(
        name="support",
        instructions="Be helpful",
        voice="verse",
        tools=[fake_tool],
        model="gpt-realtime-1.5",
    )
    assert agent.instructions == "Be helpful"
    assert agent.voice == "verse"
    assert agent.model == "gpt-realtime-1.5"
    assert agent.tools == [fake_tool]


def test_to_realtime_agent_passes_through_name_and_instructions() -> None:
    agent = Agent(name="hello", instructions="say hi")
    realtime = agent.to_realtime_agent()
    assert isinstance(realtime, RealtimeAgent)
    assert realtime.name == "hello"
    assert realtime.instructions == "say hi"


def test_to_realtime_agent_returns_a_fresh_tools_list() -> None:
    def fake_tool() -> str:
        return "x"

    agent = Agent(name="hello", tools=[fake_tool])
    realtime = agent.to_realtime_agent()
    # Mutating the SDK agent's tool list must not affect oratium.Agent.tools.
    realtime.tools.append("extra")
    assert agent.tools == [fake_tool]


def test_model_config_basic() -> None:
    agent = Agent(name="hello")
    config = agent.model_config(api_key="sk-test")

    assert config["api_key"] == "sk-test"
    settings = config["initial_model_settings"]
    assert settings["model_name"] == DEFAULT_MODEL
    assert settings["voice"] == DEFAULT_VOICE
    assert settings["input_audio_format"] == "g711_ulaw"
    assert settings["output_audio_format"] == "g711_ulaw"
    assert "playback_tracker" not in config


def test_model_config_with_playback_tracker() -> None:
    agent = Agent(name="hello")
    tracker = RealtimePlaybackTracker()
    config = agent.model_config(api_key="sk-test", playback_tracker=tracker)
    assert config["playback_tracker"] is tracker


def test_model_config_voice_and_model_overrides() -> None:
    agent = Agent(name="hello", voice="verse", model="gpt-realtime-1.5")
    config = agent.model_config(api_key="sk-test")
    assert config["initial_model_settings"]["voice"] == "verse"
    assert config["initial_model_settings"]["model_name"] == "gpt-realtime-1.5"


def test_model_config_turn_detection_defaults() -> None:
    agent = Agent(name="hello")
    config = agent.model_config(api_key="sk-test")
    td = config["initial_model_settings"]["turn_detection"]
    assert td["type"] == "semantic_vad"
    assert td["interrupt_response"] is True
    assert td["create_response"] is True


# --- Phase 4: UnifiedTools support on Agent ---


@function_tool
def _phase4_example(x: int) -> int:
    """Example tool for Phase 4 tests."""
    return x


def test_agent_accepts_list_of_callables_phase1_compat() -> None:
    """Backward compat: a bare list of function tools still works."""
    agent = Agent(name="x", tools=[_phase4_example])
    realtime = agent.to_realtime_agent()
    assert len(realtime.tools) == 1


def test_agent_accepts_unified_tools() -> None:
    agent = Agent(
        name="x",
        tools=UnifiedTools(
            functions=[_phase4_example],
            data_tables=[DataTable(name="t", rows=[{"k": "v"}])],
        ),
    )
    realtime = agent.to_realtime_agent()
    assert len(realtime.tools) == 2  # function + query_t


def test_agent_passes_mcp_servers_through_to_sdk() -> None:
    agent = Agent(
        name="x",
        tools=UnifiedTools(mcp_servers=["https://mcp.example.com"]),
    )
    realtime = agent.to_realtime_agent()
    assert len(realtime.mcp_servers) == 1


def test_agent_with_knowledge_requires_api_key() -> None:
    import pytest

    agent = Agent(name="x", tools=UnifiedTools(knowledge=["./doc.pdf"]))
    with pytest.raises(ValueError, match="api_key"):
        agent.to_realtime_agent()


def test_agent_with_knowledge_and_api_key_succeeds() -> None:
    """Construction shouldn't make any OpenAI calls; the embedder is lazy."""
    agent = Agent(name="x", tools=UnifiedTools(knowledge=["./doc.pdf"]))
    realtime = agent.to_realtime_agent(api_key="sk-test")
    assert len(realtime.tools) == 1
    assert realtime.tools[0].name == "search_knowledge"


def test_agent_empty_tools_list_yields_no_sdk_tools() -> None:
    agent = Agent(name="x")
    realtime = agent.to_realtime_agent()
    assert realtime.tools == []
    assert realtime.mcp_servers == []
