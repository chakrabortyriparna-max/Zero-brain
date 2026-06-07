"""Tests for .claude/scripts/llm_client.py."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from llm_client import LLMClient, _detect_backend, _ollama_available  # noqa: E402


class TestDetectBackend:
    @patch("llm_client._ollama_available", return_value=False)
    @patch.dict(os.environ, {}, clear=True)
    def test_no_backend_raises(self, mock_ollama):
        with pytest.raises(RuntimeError, match="No LLM backend available"):
            _detect_backend()

    @patch("llm_client._ollama_available", return_value=True)
    def test_ollama_default(self, mock_ollama):
        backend, model = _detect_backend()
        assert backend == "ollama"
        assert model == "kimi-k2.6:cloud"

    @patch("llm_client._ollama_available", return_value=False)
    @patch.dict(os.environ, {"GROQ_API_KEY": "test"})
    def test_groq_fallback(self, mock_ollama):
        backend, model = _detect_backend()
        assert backend == "groq"
        assert model == "llama-3.3-70b-versatile"

    @patch("llm_client._ollama_available", return_value=False)
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"})
    def test_anthropic_fallback(self, mock_ollama):
        backend, model = _detect_backend()
        assert backend == "anthropic"
        assert model == "claude-sonnet-4-6"

    @patch("llm_client._ollama_available", return_value=False)
    @patch.dict(os.environ, {"GROQ_API_KEY": "test"})
    def test_prefer_groq(self, mock_ollama):
        backend, model = _detect_backend(prefer="groq")
        assert backend == "groq"

    @patch("llm_client._ollama_available", return_value=False)
    def test_prefer_unavailable_raises(self, mock_ollama):
        with pytest.raises(RuntimeError, match="Preferred backend 'ollama' is not available"):
            _detect_backend(prefer="ollama")


class TestLLMClientComplete:
    @patch("llm_client._call_ollama", return_value=("hello from ollama", {"backend": "ollama", "latency_ms": 100}))
    @patch("llm_client._ollama_available", return_value=True)
    def test_complete_ollama(self, mock_avail, mock_call):
        client = LLMClient()
        result = client.complete("Say hello")
        assert result == "hello from ollama"
        assert client.last_call_info["backend"] == "ollama"
        mock_call.assert_called_once()

    @patch("llm_client._call_groq", return_value=("hello from groq", {"backend": "groq", "latency_ms": 50}))
    @patch("llm_client._ollama_available", return_value=False)
    @patch.dict(os.environ, {"GROQ_API_KEY": "test"})
    def test_complete_groq(self, mock_avail, mock_call):
        client = LLMClient()
        result = client.complete("Say hello")
        assert result == "hello from groq"
        assert client.last_call_info["backend"] == "groq"
        mock_call.assert_called_once()

    @patch("llm_client._call_ollama", side_effect=RuntimeError("Ollama down"))
    @patch("llm_client._call_groq", return_value=("hello from groq fallback", {"backend": "groq"}))
    @patch("llm_client._ollama_available", return_value=True)
    @patch.dict(os.environ, {"GROQ_API_KEY": "test"})
    def test_complete_with_fallback(self, mock_anth_avail, mock_groq_call, mock_ollama_call):
        client = LLMClient()
        result = client.complete_with_fallback("Say hello")
        assert result == "hello from groq fallback"
        assert client.last_call_info.get("fallback_from") == "ollama"

    @patch("llm_client._call_ollama", side_effect=RuntimeError("timeout"))
    @patch("llm_client._ollama_available", return_value=True)
    def test_retry_then_fail(self, mock_avail, mock_call):
        client = LLMClient()
        with pytest.raises(RuntimeError, match="LLM call failed after"):
            client.complete("Say hello")
        assert mock_call.call_count == 3

    def test_health(self):
        with patch("llm_client._ollama_available", return_value=True):
            client = LLMClient()
            health = client.health()
            assert health["backend"] == "ollama"
            assert "model" in health


class TestLLMClientChat:
    @patch("llm_client._call_ollama", return_value=("chat reply", {"backend": "ollama", "latency_ms": 100}))
    @patch("llm_client._ollama_available", return_value=True)
    def test_chat_ollama(self, mock_avail, mock_call):
        client = LLMClient()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"},
        ]
        result = client.chat(messages)
        assert result == "chat reply"
        assert client.last_call_info["backend"] == "ollama"
        # Verify messages were passed through
        call_args = mock_call.call_args
        assert call_args[0][0] == messages

    @patch("llm_client._call_anthropic", return_value=("anthropic reply", {"backend": "anthropic"}))
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"})
    def test_chat_anthropic(self, mock_call):
        client = LLMClient(backend="anthropic")
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = client.chat(messages)
        assert result == "anthropic reply"
        assert client.last_call_info["backend"] == "anthropic"
        # Verify messages were passed to the backend
        call_args = mock_call.call_args
        assert call_args[0][0] == messages

    @patch("llm_client._call_groq", return_value=("groq chat", {"backend": "groq"}))
    @patch.dict(os.environ, {"GROQ_API_KEY": "test"})
    def test_chat_with_system_override(self, mock_call):
        client = LLMClient(backend="groq")
        messages = [{"role": "user", "content": "Hello"}]
        result = client.chat(messages, system="Override system")
        assert result == "groq chat"
        # _dispatch passes system as the 4th positional arg to _call_groq
        call_args = mock_call.call_args
        assert call_args[0][3] == "Override system"

    @patch("llm_client._call_ollama", side_effect=RuntimeError("Ollama down"))
    @patch("llm_client._call_groq", return_value=("groq fallback", {"backend": "groq"}))
    @patch("llm_client._ollama_available", return_value=True)
    @patch.dict(os.environ, {"GROQ_API_KEY": "test"})
    def test_chat_with_fallback(self, mock_avail, mock_groq, mock_ollama):
        client = LLMClient()
        messages = [{"role": "user", "content": "Hello"}]
        result = client.chat_with_fallback(messages)
        assert result == "groq fallback"
        assert client.last_call_info.get("fallback_from") == "ollama"
