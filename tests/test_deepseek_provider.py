"""
Tests for backend/ai/deepseek_provider.py (#62) — DeepSeek's API is
OpenAI-compatible (chat completions), so this mirrors GrokProvider's
existing pattern: reuse the `openai` SDK pointed at DeepSeek's base_url.
No real network calls — the openai.OpenAI client is mocked.
"""
from unittest.mock import patch, MagicMock

from backend.ai.deepseek_provider import DeepSeekProvider


def _fake_openai_client(response_text):
    fake_message = MagicMock()
    fake_message.content = response_text
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response
    return fake_client


def test_no_api_key_returns_in_band_error_not_raise():
    provider = DeepSeekProvider()
    result = provider.ask("best portable generator")
    assert result.is_error is True
    assert "no API key" in result.executive_summary
    assert result.provider == "DeepSeek"


def test_successful_call_parses_response_through_ai_reasoning_parser():
    provider = DeepSeekProvider()
    provider.set_api_key("fake-key")

    json_text = (
        '{"executive_summary": "Test summary", "confidence": "High", '
        '"opportunities": [], "risks": [], "follow_up_questions": [], '
        '"supporting_evidence": []}'
    )
    with patch("openai.OpenAI", return_value=_fake_openai_client(json_text)):
        result = provider.ask("best portable generator")

    assert result.is_error is False
    assert result.executive_summary == "Test summary"
    assert result.confidence == "High"
    assert result.provider == "DeepSeek"


def test_uses_deepseek_base_url_and_configured_model():
    provider = DeepSeekProvider()
    provider.set_api_key("fake-key")
    provider.set_model("deepseek-reasoner")

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_openai_cls.return_value = _fake_openai_client('{"executive_summary": "x"}')
        provider.ask("best portable generator")

    _, kwargs = mock_openai_cls.call_args
    assert kwargs["base_url"] == "https://api.deepseek.com"
    assert kwargs["api_key"] == "fake-key"

    fake_client = mock_openai_cls.return_value
    _, call_kwargs = fake_client.chat.completions.create.call_args
    assert call_kwargs["model"] == "deepseek-reasoner"


def test_network_exception_is_reported_in_band_not_raised():
    provider = DeepSeekProvider()
    provider.set_api_key("fake-key")

    with patch("openai.OpenAI", side_effect=Exception("connection refused")):
        result = provider.ask("best portable generator")

    assert result.is_error is True
    assert "connection refused" in result.executive_summary
    assert result.provider == "DeepSeek"


def test_default_model_is_deepseek_chat():
    provider = DeepSeekProvider()
    assert provider.model == "deepseek-chat"
