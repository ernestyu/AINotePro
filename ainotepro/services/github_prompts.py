"""GitHub Contents API for the unified AINotePro library (no git/gh)."""
from __future__ import annotations

import base64
import json
import datetime
import logging
import os
import re
import sys
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..core.prompt_bundle import (
    MAX_LIBRARY_BYTES, make_bundle, merge_bundles, parse_bundle, serialize_bundle,
)

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def validate_settings(settings):
    if not isinstance(settings, dict):
        raise ValueError("GitHub settings must be an object")
    repo = str(settings.get("repository", "")).strip()
    branch = str(settings.get("branch", "main")).strip()
    path = str(settings.get("path", "ainotepro-library.json")).strip()
    if not REPO_RE.fullmatch(repo) or any(seg in (".", "..") for seg in repo.split("/")):
        raise ValueError("Repository must use owner/name, without a URL")
    if (not branch or len(branch) > 200
            or any(c in branch for c in " \n\r\t\\?*[~^:")
            or ".." in branch or branch.startswith("/") or branch.endswith("/")):
        raise ValueError("Invalid GitHub branch name")
    if (not path or len(path) > 240 or path.startswith("/") or "\\" in path
            or any(x in ("", ".", "..") for x in path.split("/"))
            or not path.lower().endswith(".json")):
        raise ValueError("Path must be a relative JSON path (for example ainotepro-library.json)")
    return {"repository": repo, "branch": branch, "path": path}


# Bounded explicit log writes (rather than logging.Handler, whose emit errors
# can be swallowed). Mirror diagnostics to stdout, NOT stderr: Anki's error
# handler treats any stderr write as an add-on exception report.
# Only allow-listed metadata is recorded, never token/header/request body.
_LOG_LOCK = threading.Lock()
_MAX_LOG_BYTES = 300_000


def diagnostic_log_path():
    from ..config.manager import USER_FILES_DIR
    return os.path.join(USER_FILES_DIR, "logs", "github_sync.log")


def _log(level, operation, cfg, status, request_id="-", note="", *, has_token=False):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    entry = (f"{now} [{logging.getLevelName(level)}] "
             f"stage={operation} status={status} request_id={request_id} "
             f"repository={cfg['repository']} branch={cfg['branch']} "
             f"path={cfg['path']} token_present={bool(has_token)} {note}")
    # Normal expected HTTP errors must not trigger Anki's stderr error popup.
    print(f"[AINotePro][GitHub] {entry}", file=sys.stdout, flush=True)
    try:
        path = diagnostic_log_path()
        encoded = (entry + "\n").encode("utf-8")
        with _LOG_LOCK:
            os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
            if (os.path.exists(path)
                    and os.path.getsize(path) + len(encoded) > _MAX_LOG_BYTES):
                # Keep two previous bounded files.
                if os.path.exists(path + ".2"):
                    os.remove(path + ".2")
                if os.path.exists(path + ".1"):
                    os.replace(path + ".1", path + ".2")
                os.replace(path, path + ".1")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "ab") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        return None
    except (OSError, ValueError) as exc:
        # Never claim diagnostics were written when they were not.
        detail = f"{type(exc).__name__}: {str(exc)[:200]}"
        print(f"[AINotePro][GitHub] Diagnostic file write FAILED: {detail}",
              file=sys.stdout, flush=True)
        return detail


class GitHubAPIError(RuntimeError):
    def __init__(self, operation, status, request_id, message, log_error=None):
        self.operation = operation
        self.status = status
        self.request_id = request_id
        self.log_error = log_error
        location = (
            f"\nDiagnostic logging failed ({log_error}). See Anki launch terminal."
            if log_error else f"\nDiagnostic log: {diagnostic_log_path()}"
        )
        super().__init__(
            f"{message} [stage={operation}, HTTP {status}, request_id={request_id}]"
            + location
        )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError("GitHub API redirect refused")


_OPENER = build_opener(_NoRedirect())


def _api_url(cfg, kind):
    root = "https://api.github.com/repos/" + "/".join(
        quote(x, safe="") for x in cfg["repository"].split("/")
    )
    if kind == "repository":
        return root
    if kind == "branch":
        return root + "/branches/" + quote(cfg["branch"], safe="")
    if kind == "contents":
        return root + "/contents/" + "/".join(
            quote(x, safe="") for x in cfg["path"].split("/")
        )
    raise ValueError("Invalid GitHub API endpoint")


def _call(cfg, token, operation, *, method="GET", payload=None):
    kind = ("repository" if operation == "check_repository"
            else "branch" if operation == "check_branch" else "contents")
    url = _api_url(cfg, kind)
    if operation == "read_file":
        url += "?" + urlencode({"ref": cfg["branch"]})
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "AINotePro-Library-Sync",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with _OPENER.open(req, timeout=20) as response:
            request_id = response.headers.get("X-GitHub-Request-Id", "-")
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("GitHub response unexpectedly large")
            result = json.loads(raw)
            _log(logging.INFO, operation, cfg, response.status, request_id,
                 "ok", has_token=bool(token))
            return result
    except HTTPError as exc:
        request_id = (exc.headers.get("X-GitHub-Request-Id", "-")
                      if exc.headers else "-")
        log_error = _log(logging.ERROR, operation, cfg, exc.code, request_id,
                         "http_error", has_token=bool(token))
        if exc.code == 404 and operation == "read_file":
            return None
        if exc.code == 404 and operation == "check_repository":
            message = ("Repository is not visible to the saved token. "
                       "For a private repository, verify the Fine-grained Token "
                       "resource owner, selected repository, and Contents permission.")
        elif exc.code == 404 and operation == "check_branch":
            message = f"Branch '{cfg['branch']}' is not accessible to the token."
        elif exc.code == 404:
            message = ("GitHub could not create/update the target file. "
                       "Check repository access and Contents read/write permissions.")
        elif exc.code in (401, 403):
            message = ("GitHub rejected authentication or permissions. "
                       "Check that the token is valid and has Contents read/write "
                       "permission for this repository.")
        elif exc.code in (409, 422) and method == "PUT":
            message = ("GitHub rejected the file update (conflict or validation). "
                       "Check the branch, target path and file revision.")
        else:
            message = "GitHub API request failed."
        raise GitHubAPIError(operation, exc.code, request_id, message,
                             log_error=log_error) from None
    except URLError as exc:
        log_error = _log(logging.ERROR, operation, cfg, "network",
                         note="connection_error", has_token=bool(token))
        raise RuntimeError(
            f"Cannot contact GitHub during {operation} (network or TLS failure).\n"
            + (f"Diagnostic logging failed ({log_error}). See terminal."
               if log_error else f"Diagnostic log: {diagnostic_log_path()}")
        ) from None


def _request(settings, token, method="GET", payload=None):
    cfg = validate_settings(settings)
    if method == "GET":
        # A 404 on Contents means either a missing file or no access to a
        # private repository. Verify repository and branch first, so we never
        # mistake an authentication problem for a first-time upload.
        _call(cfg, token, "check_repository")
        _call(cfg, token, "check_branch")
        return _call(cfg, token, "read_file")
    if method == "PUT":
        return _call(cfg, token, "create_or_update_file", method="PUT",
                     payload=payload)
    raise ValueError("Unsupported GitHub request method")


def fetch_remote(settings, token):
    doc = _request(settings, token)
    if doc is None:
        return None, None
    if not isinstance(doc, dict) or doc.get("type") != "file" or doc.get("encoding") != "base64":
        raise ValueError("GitHub path must reference a small JSON file")
    encoded = doc.get("content")
    if not isinstance(encoded, str):
        raise ValueError("GitHub response has no file content")
    try:
        raw = json.loads(base64.b64decode(encoded, validate=False).decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("GitHub file does not contain valid UTF-8 JSON") from exc
    sha = doc.get("sha")
    if not isinstance(sha, str) or not sha:
        raise ValueError("GitHub response has no file revision")
    return parse_bundle(raw), sha


def load_from_github(settings, token):
    result, _sha = fetch_remote(settings, token)
    if result is None:
        raise ValueError("No AINotePro library file found at the configured GitHub path")
    return result


def save_to_github(settings, token, local_bundle):
    if not token:
        raise ValueError("GitHub Save requires a token; enter one in GitHub Settings")
    local = parse_bundle(local_bundle)
    for attempt in range(3):
        current, sha = fetch_remote(settings, token)
        if current is None:
            current = make_bundle({}, {}, [])
        combined, stats = merge_bundles(current, local, protect_default=False)
        if sha is not None and combined == current:
            return {"changed": False, "stats": stats}
        payload = {"message": "chore(library): sync AINotePro prompts and Audio Profiles",
                   "content": base64.b64encode(
                       serialize_bundle(combined, max_bytes=MAX_LIBRARY_BYTES)
                   ).decode("ascii"),
                   "branch": validate_settings(settings)["branch"]}
        if sha is not None:
            payload["sha"] = sha
        try:
            _request(settings, token, method="PUT", payload=payload)
        except GitHubAPIError as exc:
            if exc.status in (409, 422) and attempt < 2:
                continue
            raise
        return {"changed": True, "stats": stats}
    raise RuntimeError("GitHub file was modified repeatedly; retry later")
