import pytest
from unittest.mock import MagicMock, patch
from agents.friendlyAgent import FriendlyAgent


@patch("agents.friendlyAgent.ChatOllama")
def test_init_uses_env_model(mock_llm):
    # Setup
    mock_llm.return_value = MagicMock()
    
    agent = FriendlyAgent(model_name="mock-model")

    # Check LLM initialized correctly
    mock_llm.assert_called_with(model="mock-model", temperature=0.8)
    assert agent.llm is mock_llm.return_value


@patch("agents.friendlyAgent.ChatOllama")
@patch("agents.friendlyAgent.friendly_prompt")
def test_respond_returns_llm_output(mock_prompt, mock_llm):
    mock_prompt.return_value = "THIS IS THE PROMPT"

    fake_response = MagicMock()
    fake_response.content = " hello there "
    mock_llm.return_value.invoke.return_value = fake_response

    agent = FriendlyAgent(model_name="mock-model")

    out = agent.respond("hi")
    assert out == "hello there"

    mock_prompt.assert_called_once_with("hi")
    mock_llm.return_value.invoke.assert_called_once_with("THIS IS THE PROMPT")


@patch("agents.friendlyAgent.ChatOllama")
@patch("agents.friendlyAgent.friendly_prompt")
def test_invoke_happy_path(mock_prompt, mock_llm):
    mock_prompt.return_value = "PROMPT"

    fake_response = MagicMock()
    fake_response.content = "final answer"
    mock_llm.return_value.invoke.return_value = fake_response

    agent = FriendlyAgent(model_name="mock-model")

    state = {"user_input": "yo"}
    out = agent.invoke(state)

    assert "messages" in out
    assert out["messages"][0]["content"] == "final answer"


def test_invoke_missing_user_input():
    agent = FriendlyAgent(model_name="mock-model")

    with pytest.raises(ValueError):
        agent.invoke({})  # missing user_input

