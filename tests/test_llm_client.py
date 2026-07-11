"""Unit tests for bct/llm_client.py — no real network calls, SDK clients mocked."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct import llm_client  # noqa: E402


class TestConfiguredProvider:
    def test_none_when_no_keys_set(self):
        with patch.dict(os.environ, {}, clear=True):
            assert llm_client.configured_provider() is None

    def test_detects_groq_first(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_x", "ANTHROPIC_API_KEY": "sk-ant-x"}, clear=True):
            assert llm_client.configured_provider() == "groq"

    def test_detects_anthropic_when_only_that_is_set(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-x"}, clear=True):
            assert llm_client.configured_provider() == "anthropic"


class TestGetResponse:
    @pytest.mark.asyncio
    async def test_raises_when_no_provider_configured_or_passed(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No LLM API key configured"):
                await llm_client.get_response("system", "hi")

    @pytest.mark.asyncio
    async def test_routes_to_groq(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="groq says hi"))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        with patch("groq.Groq", return_value=mock_client):
            result = await llm_client.get_response("system", "hi", provider="groq")
        assert result == "groq says hi"

    @pytest.mark.asyncio
    async def test_routes_to_anthropic(self):
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="claude says hi")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp
        with patch("anthropic.Anthropic", return_value=mock_client):
            result = await llm_client.get_response("system", "hi", provider="anthropic")
        assert result == "claude says hi"

    @pytest.mark.asyncio
    async def test_rejects_unsupported_provider(self):
        with pytest.raises(ValueError, match="Unsupported provider"):
            await llm_client.get_response("system", "hi", provider="openai-direct")
