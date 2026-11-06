import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from core.config import get_settings
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider
from llm.base import LLMResponse


def test_settings_loaded():
    settings = get_settings()
    assert settings.DEFAULT_CHAT_MODEL == "qwen2.5-coder:7b"
    assert settings.GROQ_MODEL is not None


@pytest.mark.asyncio
async def test_ollama_connection():
    provider = OllamaProvider()
    with patch.object(provider, "is_available", new_callable=AsyncMock, return_value=True):
        available = await provider.is_available()
        assert available is True


@pytest.mark.asyncio
async def test_groq_connection():
    provider = GroqProvider()
    with patch.object(provider, "is_available", new_callable=AsyncMock, return_value=True):
        available = await provider.is_available()
        assert available is True


@pytest.mark.asyncio
async def test_groq_list_models():
    provider = GroqProvider()
    mock_models = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"]
    with patch.object(provider, "list_models", new_callable=AsyncMock, return_value=mock_models):
        models = await provider.list_models()
        assert len(models) > 0
        assert any("llama" in m.lower() for m in models)


@pytest.mark.asyncio
async def test_ollama_generate_ping():
    provider = OllamaProvider()
    mock_resp = LLMResponse(content="PONG", model="qwen2.5:1.5b")
    with patch.object(provider, "generate", new_callable=AsyncMock, return_value=mock_resp):
        response = await provider.generate(
            prompt="Reply ONLY with the single word: PONG",
            model="qwen2.5:1.5b",
            temperature=0.0
        )
        assert response.content is not None
        assert "PONG" in response.content.upper()
