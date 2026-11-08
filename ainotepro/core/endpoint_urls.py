"""Single-service URL routing for Text providers.

Models discovery is derived from the chat route; a query or fragment makes
that derivation ambiguous and must not be copied into a different API request.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def normalize_local_server_address(value: str) -> str:
    """Accept a local server root, /v1 root, or a known complete API route."""
    raw = (value or "").strip()
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    path = parts.path.rstrip("/")
    for suffix in ("/v1/chat/completions", "/chat/completions",
                   "/v1/models", "/models", "/api/chat", "/api/tags"):
        if path.endswith(suffix):
            path = path[:-len(suffix)].rstrip("/")
            break
    if path.endswith("/v1"):
        path = path[:-len("/v1")]
    return urlunsplit((parts.scheme, parts.netloc, path.rstrip("/"),
                       parts.query, parts.fragment))


def local_chat_endpoint(value: str) -> str:
    """Build one /v1/chat/completions suffix before any query or fragment."""
    server = normalize_local_server_address(value)
    parts = urlsplit(server)
    path = parts.path.rstrip("/") + "/v1/chat/completions"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def legacy_chat_endpoint(base_url: str) -> str:
    """Preserve the old base_url route rule, including any path prefix."""
    base = (base_url or "").strip()
    if not base:
        return ""
    parts = urlsplit(base)
    path = parts.path.rstrip("/")
    suffix = ("/chat/completions" if path.endswith(("/v1", "/v1beta/openai"))
              else "/v1/chat/completions")
    return urlunsplit((parts.scheme, parts.netloc, path + suffix,
                       parts.query, parts.fragment))


def models_endpoint_from_chat(chat_url: str) -> str:
    """Derive Models only when the Chat URL has no ambiguous query/fragment."""
    try:
        parts = urlsplit((chat_url or "").strip())
        path = parts.path.rstrip("/")
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.query or parts.fragment
                or not path.endswith("/chat/completions")):
            return ""
        # Invalid authority syntax, including malformed ports, fails closed.
        _ = parts.port
        new_path = path[:-len("/chat/completions")] + "/models"
        return urlunsplit((parts.scheme, parts.netloc, new_path, "", ""))
    except ValueError:
        return ""
