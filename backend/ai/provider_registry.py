from backend.ai.mock_provider import MockAIProvider
from backend.ai.openai_provider import OpenAIProvider
from backend.ai.anthropic_provider import AnthropicProvider
from backend.ai.gemini_provider import GeminiProvider
from backend.ai.perplexity_provider import PerplexityProvider
from backend.ai.grok_provider import GrokProvider
from backend.ai.mistral_provider import MistralProvider
from backend.ai.deepseek_provider import DeepSeekProvider
from backend.ai.cohere_provider import CohereProvider


class ProviderRegistry:
    def __init__(self):
        self.providers = {
            "mock": MockAIProvider,
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "gemini": GeminiProvider,
            "perplexity": PerplexityProvider,
            "grok": GrokProvider,
            "mistral": MistralProvider,
            "deepseek": DeepSeekProvider,
            "cohere": CohereProvider,
        }

    def create_provider(self, provider_key):
        if provider_key not in self.providers:
            raise ValueError(f"Unknown provider: {provider_key}")
        return self.providers[provider_key]()

    def list_provider_keys(self):
        return list(self.providers.keys())

    def list_ui_provider_keys(self):
        """Provider keys shown in the live UI — excludes mock (kept for dev/testing only)."""
        return [k for k in self.providers if k != "mock"]
