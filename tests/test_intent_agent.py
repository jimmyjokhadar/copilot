import pytest
from unittest.mock import MagicMock, patch
from agents.intentAgent import IntentAgent, IntentState


@pytest.fixture
def mock_agent():
    with patch("agents.intentAgent.pymongo.MongoClient") as mongo_mock:
        mongo_db = MagicMock()
        mongo_users = MagicMock()
        mongo_mock.return_value.__getitem__.return_value = mongo_db
        mongo_db.__getitem__.return_value = mongo_users

        with patch("agents.intentAgent.ChatOllama") as llm_mock:
            llm_mock.return_value.invoke.return_value.content = "friendly_chat"
            agent = IntentAgent(user_ctx={"test": True})
            return agent


def test_graph_builds(mock_agent):
    assert mock_agent.graph is not None


def test_intent_detection(mock_agent):
    state: IntentState = {
        "user_input": "hello",
        "intent": None,
        "result": None,
        "conversation_history": [],
        "clientId": None,
        "slack_user_id": None,
        "context": None,
        "user_ctx": None,
    }

    output = mock_agent._intent_detector(state)
    assert output["intent"] == "friendly_chat"


def test_routing_friendly(mock_agent):
    assert mock_agent._route_by_intent({"intent": "friendly_chat"}) == "friendly"


def test_routing_banking(mock_agent):
    assert mock_agent._route_by_intent({"intent": "customer_request"}) == "banking"


def test_routing_fallback(mock_agent):
    assert mock_agent._route_by_intent({"intent": "weird"}) == "fallback"


@patch("agents.intentAgent.FriendlyAgent")
def test_friendly_node(mock_friendly, mock_agent):
    fake = MagicMock()
    fake.invoke.return_value = {"messages": [{"content": "hi there"}]}
    mock_friendly.return_value = fake

    state: IntentState = {
        "user_input": "yo",
        "intent": "friendly_chat",
        "result": None,
        "conversation_history": [],
        "clientId": None,
        "slack_user_id": None,
        "context": None,
        "user_ctx": None,
    }

    out = mock_agent._friendly_node(state)
    assert out["result"]["content"] == "hi there"
    assert len(out["conversation_history"]) == 2

@patch("agents.bankingAgent.BankingAgent")
def test_banking_node(mock_banking, mock_agent):
    fake = MagicMock()

    msg = MagicMock()
    msg.content = "your balance is 0$"

    fake.invoke.return_value = {
        "messages": [msg]
    }
    mock_banking.return_value = fake

    state: IntentState = {
        "user_input": "check balance",
        "intent": "customer_request",
        "result": None,
        "conversation_history": [],
        "clientId": "1234",
        "slack_user_id": "UXXX",
        "context": None,
        "user_ctx": None,
    }

    out = mock_agent._banking_node(state)
    assert out["result"]["content"] == "your balance is 0$"
    assert out["conversation_history"][1]["content"] == "your balance is 0$"


def test_fallback(mock_agent):
    state: IntentState = {
        "user_input": "random nonsense",
        "intent": "nope",
        "result": None,
        "conversation_history": [],
        "clientId": None,
        "slack_user_id": None,
        "context": None,
        "user_ctx": None,
    }

    out = mock_agent._fallback_node(state)
    assert out["result"]["content"] == "I'm sorry, I can only assist with banking-related queries."
    assert len(out["conversation_history"]) == 2
