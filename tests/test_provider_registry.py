"""
Tests for backend/ai/provider_registry.py + provider_manager.py — confirms
DeepSeek (#62) is correctly registered alongside the existing AI providers.
"""
from backend.ai.provider_registry import ProviderRegistry
from backend.ai.provider_manager import ProviderManager
from backend.ai.deepseek_provider import DeepSeekProvider


def test_registry_creates_deepseek_provider():
    registry = ProviderRegistry()
    provider = registry.create_provider("deepseek")
    assert isinstance(provider, DeepSeekProvider)


def test_deepseek_is_in_the_ui_provider_list():
    registry = ProviderRegistry()
    assert "deepseek" in registry.list_ui_provider_keys()
    assert "mock" not in registry.list_ui_provider_keys()


def test_manager_configures_deepseek_api_key_and_model():
    mgr = ProviderManager()
    mgr.set_provider_api_key("deepseek", "sk-test-key")
    mgr.set_provider_model("deepseek", "deepseek-reasoner")

    provider = mgr.get_provider("deepseek")
    assert provider.api_key == "sk-test-key"
    assert provider.model == "deepseek-reasoner"
