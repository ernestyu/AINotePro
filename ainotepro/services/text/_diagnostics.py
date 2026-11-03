"""Small, local diagnostics helpers for the two existing Text HTTP adapters."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def safe_url(url: str) -> str:
    """Return a log-only URL with its entire query (and fragment) removed."""
    try:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
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


def request_started(provider: str, model: str, method: str, url: str, config: dict) -> tuple[float, bool]:
    started = time.perf_counter()
    debug = debug_enabled(config)
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    print(f"[AINotePro] LLM request start provider={provider} model={model} method={method} "
          f"url={safe_url(url)} started_at={stamp}")
    if debug:
        print(f"[AINotePro] LLM debug request-dispatch t={started:.6f}")
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


def request_failed(provider: str, model: str, url: str, started: float, exc: Exception, debug: bool,
                   response: Any = None) -> RuntimeError:
    elapsed = time.perf_counter() - started
    summary = safe_failure(exc)
    if summary == type(exc).__name__ and response is not None:
        summary += f" HTTP {status_of(response)}"
    print(f"[AINotePro] LLM request failed provider={provider} model={model} url={safe_url(url)} "
          f"error={summary} total_ms={elapsed * 1000:.1f}")
    if debug:
        print(f"[AINotePro] LLM debug failure-after-dispatch total_ms={elapsed * 1000:.1f}")
    return RuntimeError(f"LLM request failed ({summary}); see terminal diagnostics.")
