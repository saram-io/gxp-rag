"""Multi-provider LLM Factory supporting Frontier, OpenAI-compatible, Anthropic, Gemini, and Ollama/Local models."""

import os
from typing import Any, Dict, List, Optional, Union
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.openai import OpenAIProvider

from gxp_rag.config import settings


class ModelProviderFactory:
    """Factory to create and resolve LLM model instances across various providers."""

    SUPPORTED_PRESETS: Dict[str, Dict[str, str]] = {
        "gpt-4o": {
            "display": "OpenAI GPT-4o (Frontier)",
            "model_string": "openai:gpt-4o",
            "provider": "openai",
        },
        "o3-mini": {
            "display": "OpenAI o3-mini (Reasoning)",
            "model_string": "openai:o3-mini",
            "provider": "openai",
        },
        "claude-3-7-sonnet": {
            "display": "Anthropic Claude 3.7 Sonnet (Frontier)",
            "model_string": "anthropic:claude-3-7-sonnet-latest",
            "provider": "anthropic",
        },
        "claude-3-5-sonnet": {
            "display": "Anthropic Claude 3.5 Sonnet",
            "model_string": "anthropic:claude-3-5-sonnet-latest",
            "provider": "anthropic",
        },
        "gemini-2.0-flash": {
            "display": "Google Gemini 2.0 Flash",
            "model_string": "google:gemini-2.0-flash",
            "provider": "google",
        },
        "ollama-llama3": {
            "display": "Ollama / Local (Llama 3.3)",
            "model_string": "ollama:llama3.3",
            "provider": "ollama",
        },
        "ollama-qwen": {
            "display": "Ollama / Local (Qwen 2.5 72B)",
            "model_string": "ollama:qwen2.5:72b",
            "provider": "ollama",
        },
        "ollama-deepseek-r1": {
            "display": "Ollama / Local (DeepSeek R1)",
            "model_string": "ollama:deepseek-r1",
            "provider": "ollama",
        },
        "test": {
            "display": "Deterministic Test Model",
            "model_string": "test",
            "provider": "test",
        },
    }

    @classmethod
    def create_model(
        cls,
        model_name_or_str: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Union[Model, str]:
        """Resolve model specification into a Pydantic AI Model or valid model string."""
        model_spec = model_name_or_str or settings.default_model

        # Test model
        if model_spec == "test" or model_spec.startswith("test:"):
            return TestModel()

        # Custom OpenAI-compatible endpoint (vLLM, Groq, Ollama OpenAI API, LocalAI)
        if base_url:
            api_k = api_key or os.getenv("OPENAI_API_KEY", "dummy-api-key")
            provider = OpenAIProvider(
                base_url=base_url,
                api_key=api_k,
            )
            clean_name = model_spec.split(":", 1)[-1] if ":" in model_spec else model_spec
            return OpenAIChatModel(clean_name, provider=provider)

        # Ollama native or local provider
        if model_spec.startswith("ollama:"):
            ollama_model_name = model_spec.split(":", 1)[1]
            ollama_url = os.getenv("OLLAMA_BASE_URL", settings.ollama_base_url)
            if ollama_url.endswith("/v1"):
                provider = OpenAIProvider(base_url=ollama_url, api_key="ollama")
                return OpenAIChatModel(ollama_model_name, provider=provider)
            try:
                return OllamaModel(ollama_model_name, base_url=ollama_url)
            except Exception:
                provider = OpenAIProvider(base_url=ollama_url, api_key="ollama")
                return OpenAIChatModel(ollama_model_name, provider=provider)

        # Anthropic
        if model_spec.startswith("anthropic:"):
            anthropic_model_name = model_spec.split(":", 1)[1]
            api_k = os.getenv("ANTHROPIC_API_KEY")
            if api_k:
                return AnthropicModel(anthropic_model_name)
            return model_spec

        # Google Gemini
        if model_spec.startswith("google:") or model_spec.startswith("gemini:"):
            gemini_model_name = model_spec.split(":", 1)[1]
            api_k = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if api_k:
                return GoogleModel(gemini_model_name)
            return model_spec

        # OpenAI standard
        if model_spec.startswith("openai:"):
            openai_model_name = model_spec.split(":", 1)[1]
            api_k = os.getenv("OPENAI_API_KEY")
            if api_k:
                return OpenAIChatModel(openai_model_name)
            return model_spec

        # Default string fallback recognized by Pydantic AI
        return model_spec

    @classmethod
    def create_fallback_model(
        cls,
        primary_model: Union[str, Model],
        secondary_model: Union[str, Model],
    ) -> FallbackModel:
        """Create a resilient FallbackModel with primary and backup providers."""
        # For FallbackModel, ensure valid Model instances (with dummy key fallback if offline)
        if isinstance(primary_model, str):
            if primary_model == "test":
                prim = TestModel()
            elif primary_model.startswith("openai:"):
                prim = OpenAIChatModel(primary_model.split(":", 1)[1], provider=OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY", "dummy-key")))
            else:
                prim = TestModel()
        else:
            prim = primary_model

        if isinstance(secondary_model, str):
            if secondary_model == "test":
                sec = TestModel()
            elif secondary_model.startswith("openai:"):
                sec = OpenAIChatModel(secondary_model.split(":", 1)[1], provider=OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY", "dummy-key")))
            else:
                sec = TestModel()
        else:
            sec = secondary_model

        return FallbackModel(prim, sec)

    @classmethod
    def list_available_presets(cls) -> List[Dict[str, str]]:
        """List configured model presets."""
        presets = []
        for key, info in cls.SUPPORTED_PRESETS.items():
            presets.append({
                "id": key,
                "display": info["display"],
                "model_string": info["model_string"],
                "provider": info["provider"],
            })
        return presets
