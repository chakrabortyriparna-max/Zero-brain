#!/usr/bin/env python3
"""
Shared LLM client for Second Brain scripts.

Supports Anthropic, Groq, and Ollama backends.
Auto-detects available backends in priority order:
  1. Ollama (local, free — default)
  2. Groq (fast, cheap)
  3. Anthropic (best quality)

Features:
  - Retry with exponential backoff
  - Fallback chain: if primary backend fails, try next available
  - Cost / token tracking
  - Configurable timeouts
  - Multi-turn conversation via ``chat()``

Usage:
    from llm_client import LLMClient
    client = LLMClient()               # auto-detect backend
    text = client.complete("Summarize this email...")

    # Multi-turn conversation
    response = client.chat([
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
    ])
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
DEFAULT_OLLAMA_MODEL = "kimi-k2.6:cloud"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

RETRY_ATTEMPTS = int(os.environ.get("LLM_RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF = int(os.environ.get("LLM_RETRY_BACKOFF", "2"))
REQUEST_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))


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
    if prefer and prefer != "auto":
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


def _retryable_error(exc: Exception) -> bool:
    """Determine if an exception warrants a retry."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (429, 500, 502, 503, 504)
    if isinstance(exc, RuntimeError):
        msg = str(exc).lower()
        return any(k in msg for k in ("timeout", "connection", "rate limit", "temporarily"))
    return False


def _build_metadata(backend: str, model: str, latency_ms: int, tokens: int = 0) -> dict:
    return {
        "backend": backend,
        "model": model,
        "latency_ms": latency_ms,
        "tokens": tokens,
        "success": True,
    }


def _call_anthropic(
    messages: list[dict],
    model: str,
    max_tokens: int,
    system: Optional[str] = None,
) -> tuple[str, dict]:
    """Call Anthropic Messages API with conversation history. Returns (text, metadata)."""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    api_key = os.environ["ANTHROPIC_API_KEY"]
    client = Anthropic(api_key=api_key)

    # Anthropic expects system as a top-level kwarg, not a message role.
    extracted_system = ""
    conversation_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            extracted_system = msg.get("content", "")
        else:
            conversation_messages.append(msg)

    final_system = system if system is not None else extracted_system

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": conversation_messages,
    }
    if final_system:
        kwargs["system"] = final_system

    start = time.perf_counter()
    response = client.messages.create(**kwargs)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    text = ""
    if response.content:
        text = "\n".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )

    usage = getattr(response, "usage", None)
    tokens = 0
    if usage:
        tokens = getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)

    return text, _build_metadata("anthropic", model, elapsed_ms, tokens)


def _call_groq(
    messages: list[dict],
    model: str,
    max_tokens: int,
    system: Optional[str] = None,
) -> tuple[str, dict]:
    """Call Groq Chat Completions API with conversation history. Returns (text, metadata)."""
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    api_key = os.environ["GROQ_API_KEY"]
    client = Groq(api_key=api_key)

    request_messages: list[dict] = []
    if system:
        request_messages.append({"role": "system", "content": system})
    request_messages.extend(messages)

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=request_messages,
        temperature=0.2,
        max_tokens=max_tokens,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    text = response.choices[0].message.content if response.choices else ""
    tokens = response.usage.total_tokens if response.usage else 0

    return text, _build_metadata("groq", model, elapsed_ms, tokens)


def _call_ollama(
    messages: list[dict],
    model: str,
    max_tokens: int,
    base_url: str,
    system: Optional[str] = None,
) -> tuple[str, dict]:
    """Call Ollama API with conversation history. Returns (text, metadata)."""
    url = f"{base_url}/v1/chat/completions"

    request_messages: list[dict] = []
    if system:
        request_messages.append({"role": "system", "content": system})
    request_messages.extend(messages)

    payload = {
        "model": model,
        "messages": request_messages,
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

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama API error {e.code}: {e.read().decode('utf-8')}")

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    text = ""
    tokens = 0
    if "choices" in body and body["choices"]:
        text = body["choices"][0].get("message", {}).get("content", "")
    if "usage" in body:
        tokens = body["usage"].get("total_tokens", 0)

    return text, _build_metadata("ollama", model, elapsed_ms, tokens)


class LLMClient:
    """
    Unified LLM client with auto-detection, retry, fallback, and cost tracking.

    Attributes:
        backend: 'ollama', 'groq', or 'anthropic'
        model: model name string
        base_url: Ollama base URL (only used for ollama backend)
        last_call_info: dict from last completion with latency, tokens, backend
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
        self.last_call_info: dict = {}

    def _dispatch(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        backend_override: Optional[str] = None,
    ) -> tuple[str, dict]:
        """Dispatch to a specific backend."""
        backend = backend_override or self.backend
        if backend == "anthropic":
            return _call_anthropic(messages, self.model, max_tokens, system)
        if backend == "groq":
            return _call_groq(messages, self.model, max_tokens, system)
        if backend == "ollama":
            return _call_ollama(messages, self.model, max_tokens, self.base_url, system)
        raise RuntimeError(f"Unknown backend: {backend}")

    def _run_with_retry(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        backend_override: Optional[str] = None,
    ) -> str:
        """Execute dispatch with retry on current backend."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                text, meta = self._dispatch(messages, system, max_tokens, backend_override)
                self.last_call_info = meta
                return text
            except Exception as exc:
                last_exc = exc
                if _retryable_error(exc) and attempt < RETRY_ATTEMPTS:
                    wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                    print(
                        f"[llm_client] {self.backend} call failed (attempt {attempt}/{RETRY_ATTEMPTS}): {exc}. "
                        f"Retrying in {wait}s...",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                else:
                    break

        self.last_call_info = {
            "backend": backend_override or self.backend,
            "model": self.model,
            "success": False,
            "error": str(last_exc),
        }
        raise RuntimeError(f"LLM call failed after {RETRY_ATTEMPTS} attempts: {last_exc}")

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Send a prompt and return the generated text (with retry on current backend)."""
        messages = [{"role": "user", "content": prompt}]
        return self._run_with_retry(messages, system=system, max_tokens=max_tokens)

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a conversation history and return the assistant's response.

        Args:
            messages: List of dicts with 'role' and 'content' keys.
                      Example: [{"role": "user", "content": "Hello"},
                                {"role": "assistant", "content": "Hi there!"},
                                {"role": "user", "content": "How are you?"}]
            system: Optional system prompt.
            max_tokens: Maximum tokens to generate.

        Returns:
            The assistant's response text.
        """
        return self._run_with_retry(messages, system=system, max_tokens=max_tokens)

    def complete_with_fallback(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Complete with fallback chain.
        Tries current backend first (with retry), then falls back to other available backends.
        """
        try:
            return self.complete(prompt, system=system, max_tokens=max_tokens)
        except RuntimeError:
            pass

        messages = [{"role": "user", "content": prompt}]
        return self._try_fallback(messages, system=system, max_tokens=max_tokens)

    def chat_with_fallback(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Chat with fallback chain.
        Tries current backend first (with retry), then falls back to other available backends.
        """
        try:
            return self.chat(messages, system=system, max_tokens=max_tokens)
        except RuntimeError:
            pass

        return self._try_fallback(messages, system=system, max_tokens=max_tokens)

    def _try_fallback(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Internal fallback logic shared by complete_with_fallback and chat_with_fallback."""
        all_backends = ["ollama", "groq", "anthropic"]
        for fallback_backend in all_backends:
            if fallback_backend == self.backend:
                continue
            avail = (
                _ollama_available(self.base_url) if fallback_backend == "ollama"
                else _groq_available() if fallback_backend == "groq"
                else _anthropic_available()
            )
            if not avail:
                continue
            try:
                print(
                    f"[llm_client] Falling back to {fallback_backend}...",
                    file=sys.stderr,
                )
                text, meta = self._dispatch(messages, system, max_tokens, fallback_backend)
                meta["fallback_from"] = self.backend
                self.last_call_info = meta
                return text
            except Exception as exc:
                print(
                    f"[llm_client] Fallback {fallback_backend} also failed: {exc}",
                    file=sys.stderr,
                )
                continue

        raise RuntimeError("All LLM backends failed.")

    def health(self) -> dict:
        """Return current backend status with liveness checks."""
        return {
            "backend": self.backend,
            "model": self.model,
            "ollama_url": self.base_url,
            "ollama_reachable": _ollama_available(self.base_url),
            "groq_ready": _groq_available(),
            "anthropic_ready": _anthropic_available(),
            "last_call": self.last_call_info,
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
        print("[llm_client] Last call info:", client.last_call_info)
    except Exception as e:
        print(f"[llm_client] Test failed: {e}")

    # Multi-turn chat test
    try:
        result = client.chat(
            [
                {"role": "user", "content": "Say 'hello' and nothing else."},
            ],
            max_tokens=50,
        )
        print(f"[llm_client] Chat response: {result.strip()}")
    except Exception as e:
        print(f"[llm_client] Chat test failed: {e}")


if __name__ == "__main__":
    _demo()
