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
        assert model == "llama3.2"

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
    @patch("llm_client._call_ollama", return_value="hello from ollama")
    @patch("llm_client._ollama_available", return_value=True)
    def test_complete_ollama(self, mock_avail, mock_call):
        client = LLMClient()
        result = client.complete("Say hello")
        assert result == "hello from ollama"
        mock_call.assert_called_once()

    @patch("llm_client._call_groq", return_value="hello from groq")
    @patch("llm_client._ollama_available", return_value=False)
    @patch.dict(os.environ, {"GROQ_API_KEY": "test"})
    def test_complete_groq(self, mock_avail, mock_call):
        client = LLMClient()
        result = client.complete("Say hello")
        assert result == "hello from groq"
        mock_call.assert_called_once()

    def test_health(self):
        with patch("llm_client._ollama_available", return_value=True):
            client = LLMClient()
            health = client.health()
            assert health["backend"] == "ollama"
            assert "model" in health
