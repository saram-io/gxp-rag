"""Tests for Multi-Model Provider Factory."""

import os
import pytest
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel

from gxp_rag.models.provider_factory import ModelProviderFactory


def test_model_provider_factory_resolution():
    # TestModel
    test_m = ModelProviderFactory.create_model("test")
    assert isinstance(test_m, TestModel)

    # OpenAI model spec
    openai_m = ModelProviderFactory.create_model("openai:gpt-4o")
    assert openai_m == "openai:gpt-4o" or isinstance(openai_m, OpenAIChatModel)

    # Anthropic model spec
    anthropic_m = ModelProviderFactory.create_model("anthropic:claude-3-7-sonnet-latest")
    assert anthropic_m == "anthropic:claude-3-7-sonnet-latest" or hasattr(anthropic_m, "model_name")

    # Google model spec
    gemini_m = ModelProviderFactory.create_model("google:gemini-2.0-flash")
    assert gemini_m == "google:gemini-2.0-flash" or hasattr(gemini_m, "model_name")

    # Ollama model (OpenAI-compatible)
    ollama_m = ModelProviderFactory.create_model("ollama:llama3.3")
    assert isinstance(ollama_m, OpenAIChatModel)

    # Custom base_url endpoint (vLLM / Groq / LocalAI)
    custom_m = ModelProviderFactory.create_model(
        "deepseek-r1",
        base_url="http://localhost:8080/v1",
        api_key="custom-key",
    )
    assert isinstance(custom_m, OpenAIChatModel)


def test_fallback_model_creation():
    fb = ModelProviderFactory.create_fallback_model(
        primary_model="test",
        secondary_model="test",
    )
    assert isinstance(fb, FallbackModel)


def test_list_presets():
    presets = ModelProviderFactory.list_available_presets()
    assert len(presets) >= 5
    ids = [p["id"] for p in presets]
    assert "gpt-4o" in ids
    assert "claude-3-7-sonnet" in ids
    assert "ollama-llama3" in ids
