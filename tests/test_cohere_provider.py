"""
Tests for backend/ai/cohere_provider.py (#79) — Cohere's own SDK (ClientV2.chat),
not OpenAI-compatible. No real network calls — cohere.ClientV2 is mocked.
"""
from unittest.mock import patch, MagicMock

from backend.ai.cohere_provider import CohereProvider


def _fake_cohere_client(response_text):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = response_text

    fake_message = MagicMock()
    fake_message.content = [fake_block]

    fake_response = MagicMock()
    fake_response.message = fake_message

    fake_client = MagicMock()
    fake_client.chat.return_value = fake_response
    return fake_client


def test_no_api_key_returns_in_band_error_not_raise():
    provider = CohereProvider()
    result = provider.ask("best portable generator")
    assert result.is_error is True
    assert "no API key" in result.executive_summary
    assert result.provider == "Cohere"


def test_successful_call_parses_response_through_ai_reasoning_parser():
    provider = CohereProvider()
    provider.set_api_key("fake-key")

    json_text = (
        '{"executive_summary": "Test summary", "confidence": "High", '
        '"opportunities": [], "risks": [], "follow_up_questions": [], '
        '"supporting_evidence": []}'
    )
    with patch("cohere.ClientV2", return_value=_fake_cohere_client(json_text)):
        result = provider.ask("best portable generator")

    assert result.is_error is False
    assert result.executive_summary == "Test summary"
    assert result.confidence == "High"
    assert result.provider == "Cohere"


def test_uses_configured_api_key_and_model():
    provider = CohereProvider()
    provider.set_api_key("fake-key")
    provider.set_model("command-r")

    with patch("cohere.ClientV2") as mock_cohere_cls:
        mock_cohere_cls.return_value = _fake_cohere_client('{"executive_summary": "x"}')
        provider.ask("best portable generator")

    _, kwargs = mock_cohere_cls.call_args
    assert kwargs["api_key"] == "fake-key"

    fake_client = mock_cohere_cls.return_value
    _, call_kwargs = fake_client.chat.call_args
    assert call_kwargs["model"] == "command-r"
    assert call_kwargs["messages"] == [{"role": "user", "content": "best portable generator"}]


def test_network_exception_is_reported_in_band_not_raised():
    provider = CohereProvider()
    provider.set_api_key("fake-key")

    with patch("cohere.ClientV2", side_effect=Exception("connection refused")):
        result = provider.ask("best portable generator")

    assert result.is_error is True
    assert "connection refused" in result.executive_summary
    assert result.provider == "Cohere"


def test_default_model_is_command_r_plus():
    provider = CohereProvider()
    assert provider.model == "command-r-plus"
