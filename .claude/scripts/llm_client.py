#!/usr/bin/env python3
"""
Shared LLM client for Second Brain scripts.

Supports Anthropic, Groq, and Ollama backends.
Auto-detects available backends in priority order:
  1. Ollama (local, free — default)
  2. Groq (fast, cheap)
  3. Anthropic (best quality)

Usage:
    from llm_client import LLMClient
    client = LLMClient()               # auto-detect backend
    text = client.complete("Summarize this email...")

    # Force a specific backend
    client = LLMClient(backend="anthropic", model="claude-sonnet-4-6")
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


def _ollama_available(base_url: str = DEFAULT_OLLAMA_URL) -> bool:
    """Ping Ollama to see if it's running."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _groq_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _anthropic_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _detect_backend(prefer: Optional[str] = None) -> tuple[str, str]:
    """Return (backend_name, default_model)."""
    if prefer:
        if prefer == "ollama" and _ollama_available():
            return ("ollama", DEFAULT_OLLAMA_MODEL)
        if prefer == "groq" and _groq_available():
            return ("groq", DEFAULT_GROQ_MODEL)
        if prefer == "anthropic" and _anthropic_available():
            return ("anthropic", DEFAULT_ANTHROPIC_MODEL)
        raise RuntimeError(f"Preferred backend '{prefer}' is not available.")

    if _ollama_available():
        return ("ollama", DEFAULT_OLLAMA_MODEL)
    if _groq_available():
        return ("groq", DEFAULT_GROQ_MODEL)
    if _anthropic_available():
        return ("anthropic", DEFAULT_ANTHROPIC_MODEL)

    raise RuntimeError(
        "No LLM backend available. "
        "Start Ollama, or set GROQ_API_KEY or ANTHROPIC_API_KEY in .env"
    )


def _call_anthropic(system: Optional[str], user: str, model: str, max_tokens: int) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    api_key = os.environ["ANTHROPIC_API_KEY"]
    client = Anthropic(api_key=api_key)
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    if not response.content:
        return ""
    return "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def _call_groq(system: Optional[str], user: str, model: str, max_tokens: int) -> str:
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    api_key = os.environ["GROQ_API_KEY"]
    client = Groq(api_key=api_key)
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content if response.choices else ""


def _call_ollama(
    system: Optional[str], user: str, model: str, max_tokens: int, base_url: str
) -> str:
    url = f"{base_url}/v1/chat/completions"
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama API error {e.code}: {e.read().decode('utf-8')}")

    if "choices" in body and body["choices"]:
        return body["choices"][0].get("message", {}).get("content", "")
    return ""


class LLMClient:
    """
    Unified LLM client with auto-detection and manual override.

    Attributes:
        backend: 'ollama', 'groq', or 'anthropic'
        model: model name string
        base_url: Ollama base URL (only used for ollama backend)
    """

    def __init__(
        self,
        backend: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = DEFAULT_OLLAMA_URL,
    ):
        self.backend, default_model = _detect_backend(prefer=backend)
        self.model = model or default_model
        self.base_url = base_url

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Send a prompt and return the generated text."""
        if self.backend == "anthropic":
            return _call_anthropic(system, prompt, self.model, max_tokens)
        if self.backend == "groq":
            return _call_groq(system, prompt, self.model, max_tokens)
        if self.backend == "ollama":
            return _call_ollama(system, prompt, self.model, max_tokens, self.base_url)
        raise RuntimeError(f"Unknown backend: {self.backend}")

    def health(self) -> dict:
        """Return current backend status."""
        return {
            "backend": self.backend,
            "model": self.model,
            "ollama_url": self.base_url,
        }


def _demo():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    client = LLMClient()
    print(f"[llm_client] Backend: {client.backend}, Model: {client.model}")
    print("[llm_client] Health:", client.health())

    # Simple completion test
    try:
        result = client.complete("Say 'ok' and nothing else.", max_tokens=50)
        print(f"[llm_client] Test response: {result.strip()}")
    except Exception as e:
        print(f"[llm_client] Test failed: {e}")


if __name__ == "__main__":
    _demo()
