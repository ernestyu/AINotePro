"""GitHub Contents API for one small prompt JSON; no git/gh dependency."""
from __future__ import annotations

import base64
import json
import re
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
    path = str(settings.get("path", "prompts.json")).strip()
    if not REPO_RE.fullmatch(repo) or any(seg in (".", "..") for seg in repo.split("/")):
        raise ValueError("Repository must use owner/name, without a URL")
    if (not branch or len(branch) > 200
            or any(c in branch for c in " \n\r\t\\?*[~^:")
            or ".." in branch or branch.startswith("/") or branch.endswith("/")):
        raise ValueError("Invalid GitHub branch name")
    if (not path or len(path) > 240 or path.startswith("/") or "\\" in path
            or any(x in ("", ".", "..") for x in path.split("/"))
            or not path.lower().endswith(".json")):
        raise ValueError("Path must be a relative JSON path (for example prompts.json)")
    return {"repository": repo, "branch": branch, "path": path}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError("GitHub API redirect refused")


_OPENER = build_opener(_NoRedirect())


def _request(settings, token, method="GET", payload=None):
    cfg = validate_settings(settings)
    url = ("https://api.github.com/repos/"
           + "/".join(quote(x, safe="") for x in cfg["repository"].split("/"))
           + "/contents/"
           + "/".join(quote(x, safe="") for x in cfg["path"].split("/")))
    if method == "GET":
        url += "?" + urlencode({"ref": cfg["branch"]})
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "AINotePro-Prompt-Sync",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with _OPENER.open(req, timeout=20) as response:
            result = response.read(2_000_000)
            if len(result) >= 2_000_000:
                raise ValueError("GitHub response is unexpectedly large")
            return json.loads(result)
    except HTTPError as exc:
        if exc.code == 404 and method == "GET":
            return None
        if exc.code in (409, 422) and method == "PUT":
            raise RuntimeError("GitHub file changed during Save or update was rejected; retry Save") from exc
        if exc.code in (401, 403):
            raise RuntimeError("GitHub authentication/permission denied; check token and Contents permissions") from exc
        if exc.code == 404:
            raise RuntimeError("GitHub repository/branch/file not found or access denied") from exc
        raise RuntimeError(f"GitHub API failed (HTTP {exc.code})") from exc
    except URLError as exc:
        raise RuntimeError("Cannot reach GitHub API; check network access") from exc


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
        raise ValueError("No prompts JSON file found at the configured GitHub path")
    return result


def save_to_github(settings, token, local_bundle):
    if not token:
        raise ValueError("GitHub Save requires a token; enter one in GitHub Settings")
    local = parse_bundle(local_bundle)
    for attempt in range(3):
        current, sha = fetch_remote(settings, token)
        if current is None:
            current = make_bundle({}, {})
        combined, stats = merge_bundles(current, local, protect_default=False)
        if sha is not None and combined == current:
            return {"changed": False, "stats": stats}
        payload = {"message": "chore(prompts): sync AINotePro prompt library",
                   "content": base64.b64encode(
                       serialize_bundle(combined, max_bytes=MAX_LIBRARY_BYTES)
                   ).decode("ascii"),
                   "branch": validate_settings(settings)["branch"]}
        if sha is not None:
            payload["sha"] = sha
        try:
            _request(settings, token, method="PUT", payload=payload)
        except RuntimeError as exc:
            if "file changed" in str(exc) and attempt < 2:
                continue
            raise
        return {"changed": True, "stats": stats}
    raise RuntimeError("GitHub file was modified repeatedly; retry later")
