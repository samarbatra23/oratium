from agents.realtime import RealtimeAgent, RealtimePlaybackTracker

from oratium.agent import DEFAULT_MODEL, DEFAULT_VOICE, Agent


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
