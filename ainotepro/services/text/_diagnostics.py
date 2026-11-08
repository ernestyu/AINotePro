"""Small, local diagnostics helpers for the two existing Text HTTP adapters."""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def safe_url(url: str) -> str:
    """Log host, port and path without URL userinfo, query or fragment."""
    try:
        parts = urlsplit(str(url))
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return "<invalid-url>"
        host = parts.hostname
        if ":" in host:  # IPv6 authorities need brackets.
            host = "[" + host + "]"
        port = parts.port  # Raises ValueError for invalid or ambiguous ports.
        authority = host + (f":{port}" if port is not None else "")
        return urlunsplit((parts.scheme, authority, parts.path, "", ""))
    except (TypeError, ValueError):
        return "<invalid-url>"


def debug_enabled(config: dict) -> bool:
    return bool((config or {}).get("debug_logging")) or os.environ.get("AINOTEPRO_DEBUG") == "1"


def status_of(response: Any) -> str:
    status = getattr(response, "status_code", None)
    return str(status) if status is not None else "unknown"


def safe_failure(exc: Exception) -> str:
    """Never pass an exception's potentially credential-bearing message on."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"{type(exc).__name__}" + (f" HTTP {status}" if status is not None else "")


def request_started(provider: str, model: str, method: str, url: str, config: dict,
                    body: dict) -> tuple[float, bool]:
    started = time.perf_counter()
    debug = debug_enabled(config)
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    print(f"[AINotePro] LLM request start provider={provider} model={model} method={method} "
          f"url={safe_url(url)} started_at={stamp}")
    if debug:
        print(f"[AINotePro] LLM debug request-dispatch t={started:.6f}")
        temperature = body.get("temperature", (body.get("options") or {}).get("temperature", "server_default"))
        reasoning = [(name, body[name]) for name in ("reasoning_effort", "thinking", "think") if name in body]
        reasoning_text = ", ".join(f"{name}={value!r}" for name, value in reasoning) or "server_default"
        print(f"[AINotePro] LLM debug request-body temperature={temperature!r} reasoning={reasoning_text} "
              f"max_tokens={body.get('max_tokens', 'server_default')!r} stream={body.get('stream', 'server_default')!r}")
    return started, debug


def request_http_returned(started: float, response: Any, debug: bool) -> float:
    elapsed = time.perf_counter() - started
    if debug:
        print(f"[AINotePro] LLM debug http-returned status={status_of(response)} http_ms={elapsed * 1000:.1f}")
    return elapsed


def request_finished(provider: str, model: str, url: str, response: Any, started: float,
                     http_elapsed: float, content: str, data: Any, debug: bool) -> None:
    total = time.perf_counter() - started
    processing = max(0.0, total - http_elapsed)
    usage = data.get("usage") if isinstance(data, dict) else None
    usage_text = ""
    if isinstance(usage, dict):
        input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        pairs = []
        if input_tokens is not None:
            pairs.append(f"input_tokens={input_tokens}")
        if output_tokens is not None:
            pairs.append(f"output_tokens={output_tokens}")
        if pairs:
            usage_text = " " + " ".join(pairs)
    print(f"[AINotePro] LLM request complete provider={provider} model={model} status={status_of(response)} "
          f"url={safe_url(url)} http_ms={http_elapsed * 1000:.1f} total_ms={total * 1000:.1f} "
          f"chars={len(content)}{usage_text}")
    if debug:
        print(f"[AINotePro] LLM debug response-processed processing_ms={processing * 1000:.1f}")


class ProviderRequestError(RuntimeError):
    """Safe, structured HTTP failure; the raw response is never exposed."""

    def __init__(self, category: str, http_status: int | None,
                 service_code: str, safe_summary: str):
        self.category = category
        self.http_status = http_status
        self.service_code = service_code
        self.safe_summary = safe_summary
        super().__init__(f"LLM request failed ({safe_summary}); see terminal diagnostics.")


_LIMIT_CODES = frozenset({
    "context_length_exceeded", "context_window_exceeded",
    "context_length_error", "maximum_context_length_exceeded",
    "prompt_too_long", "input_too_long", "input_length_exceeded",
    "max_tokens_exceeded", "max_output_tokens_exceeded",
    "output_token_limit_exceeded", "token_limit_exceeded",
})
_MODEL_CODES = frozenset({"model_not_found", "model_not_available",
                          "invalid_model", "unknown_model", "endpoint_not_found"})


def _structured_error_code(response: Any) -> str:
    """Only bounded, syntactically safe structured codes are admissible."""
    if response is None:
        return ""
    try:
        body = response.json()
        if not isinstance(body, dict):
            return ""
        obj = body.get("error")
        if not isinstance(obj, dict):
            obj = body
        code = obj.get("code") or obj.get("type")
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", code):
            return code.lower()
    except (ValueError, TypeError, AttributeError):
        pass
    return ""


def _failure_category(exc: Exception, status: int | None, code: str) -> str:
    if code in _LIMIT_CODES:
        return "context-or-output-limit"
    if status in (401, 403):
        return "auth"
    if code in _MODEL_CODES or status == 404:
        return "invalid-model-or-endpoint"
    if status in (408, 425, 429) or (status is not None and 500 <= status < 600):
        return "retryable"
    if type(exc).__name__ in {"Timeout", "ConnectTimeout", "ReadTimeout",
                              "ConnectionError", "ConnectError"}:
        return "retryable"
    return "unknown"


def request_failed(provider: str, model: str, url: str, started: float,
                   exc: Exception, debug: bool, response: Any = None) -> ProviderRequestError:
    elapsed = time.perf_counter() - started
    status = getattr(response, "status_code", None)
    if not isinstance(status, int):
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if not isinstance(status, int):
        status = None
    code = _structured_error_code(response)
    category = _failure_category(exc, status, code)
    status_part = f"HTTP {status}" if status is not None else type(exc).__name__
    code_part = f", code={code}" if code else ""
    # Never interpolate an untrusted service message, endpoint query,
    # credentials, request prompt, or model-generated content.
    summary = f"{category}: {status_part}{code_part}"[:160]
    print(f"[AINotePro] LLM request failed provider={provider} model={model} "
          f"url={safe_url(url)} error={summary} total_ms={elapsed * 1000:.1f}")
    if debug:
        print(f"[AINotePro] LLM debug failure-after-dispatch total_ms={elapsed * 1000:.1f}")
    return ProviderRequestError(category, status, code, summary)
