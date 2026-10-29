"""Dependency-free Gradio queued-call adapter for the local Kokoro service.

IMPORTANT: This is a provisional transport implementation. The user requested that
no tests be run in this development pass. Real Gradio and Anki validation is required
before release; never treat this module as already end-to-end verified.
"""
from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

PREFIXES = ("af_", "am_", "bf_", "bm_")
MAX_MP3 = 20 * 1024 * 1024
MAX_TEXT = 6000


class KokoroError(RuntimeError):
    pass


def _base_url(url):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost")
            or parts.username or parts.password or parts.path not in ("", "/")
            or parts.query or parts.fragment or not parts.port and parts.netloc.endswith(":")):
        raise KokoroError("Only local loopback HTTP Gradio endpoints are permitted")
    try:
        if parts.hostname == "localhost":
            addresses = socket.getaddrinfo(parts.hostname, parts.port or 80)
            if any(addr[4][0] not in ("127.0.0.1", "::1") for addr in addresses):
                raise KokoroError("localhost must resolve only to loopback")
    except OSError as exc:
        raise KokoroError("Cannot resolve local Kokoro host") from exc
    return f"http://{parts.hostname}:{parts.port or 80}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise KokoroError("Gradio redirect rejected")


_OPENER = urllib.request.build_opener(_NoRedirect)


def _request(url, method="GET", data=None, timeout=10, limit=2 * 1024 * 1024):
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"} if body else {})
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise KokoroError("Gradio response exceeds size limit")
            return raw
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise KokoroError(f"Gradio {method} failed: {exc}") from exc


def _json(url, method="GET", data=None, timeout=10):
    try:
        return json.loads(_request(url, method, data, timeout))
    except (UnicodeError, ValueError) as exc:
        raise KokoroError("Invalid Gradio JSON response") from exc


def _endpoint(info):
    named = info.get("named_endpoints", {})
    if not isinstance(named, dict):
        raise KokoroError("Gradio named_endpoints missing")
    ep = named.get("/synthesize") or named.get("synthesize")
    if not isinstance(ep, dict):
        raise KokoroError("Expected /synthesize endpoint is missing")
    params = ep.get("parameters", [])
    if [p.get("parameter_name") for p in params] != ["text", "voice", "speed"]:
        raise KokoroError("Incompatible /synthesize input schema")
    returns = ep.get("returns", [])
    if len(returns) != 3:
        raise KokoroError("Incompatible /synthesize output count")
    return params


def _voices(params):
    voice = params[1]
    candidates = []
    for value in (voice.get("type", {}).get("enum", []) if isinstance(voice.get("type"), dict) else [],
                  voice.get("component", {}).get("props", {}).get("choices", []) if isinstance(voice.get("component"), dict) else []):
        if isinstance(value, list):
            candidates.extend(value)
    names = []
    for entry in candidates:
        item = entry[-1] if isinstance(entry, (list, tuple)) and entry else entry
        if isinstance(item, str) and item.startswith(PREFIXES) and re.fullmatch(r"[ab][fm]_[a-z0-9_]+", item):
            names.append(item)
    return sorted(set(names))


class KokoroGradioProvider:
    def probe(self, config):
        base = _base_url(config.get("base_url", "http://127.0.0.1:7860"))
        try:
            info = _json(base + "/gradio_api/info", timeout=10)
        except KokoroError:
            info = _json(base + "/info", timeout=10)
        params = _endpoint(info)
        voices = _voices(params)
        if not voices:
            # Gradio versions may put choices only in /config components.
            cfg = _json(base + "/config", timeout=10)
            for comp in cfg.get("components", []):
                props = comp.get("props") or {}
                if str(comp.get("type", "")).lower() == "dropdown" or props.get("choices"):
                    for item in props.get("choices", []):
                        name = item[-1] if isinstance(item, (list, tuple)) and item else item
                        if isinstance(name, str) and name.startswith(PREFIXES):
                            voices.append(name)
        voices = sorted(set(v for v in voices if re.fullmatch(r"[ab][fm]_[a-z0-9_]+", v)))
        if not voices:
            raise KokoroError("No English voices exposed by Kokoro Gradio")
        return voices

    def generate(self, text, config):
        text = str(text or "").strip()
        voice = str(config.get("voice", ""))
        speed = float(config.get("speed", 1.0))
        if not text or len(text) > MAX_TEXT:
            raise KokoroError("Kokoro text must contain 1–6000 characters")
        if not re.fullmatch(r"(af|am|bf|bm)_[a-z0-9_]+", voice) or not 0.7 <= speed <= 1.3:
            raise KokoroError("Invalid Kokoro English voice or speed")
        base = _base_url(config.get("base_url", "http://127.0.0.1:7860"))
        deadline = time.monotonic() + 420
        event = _json(base + "/gradio_api/call/synthesize", method="POST",
                      data={"data": [text, voice, speed]}, timeout=15)
        event_id = event.get("event_id") if isinstance(event, dict) else None
        if not isinstance(event_id, str) or not re.fullmatch(r"[\w-]{1,128}", event_id):
            raise KokoroError("Gradio queue did not return a valid event_id")
        url = base + "/gradio_api/call/synthesize/" + urllib.parse.quote(event_id)
        # SSE response is a stream; avoid buffering an entire potentially long queue.
        req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
        try:
            with _OPENER.open(req, timeout=120) as response:
                current_event, lines = "", []
                for raw in response:
                    if time.monotonic() > deadline:
                        raise KokoroError("Kokoro overall deadline exceeded")
                    line = raw.decode("utf-8", "replace").strip()
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        lines.append(line[5:].strip())
                    elif not line and lines:
                        payload = "\n".join(lines)
                        lines = []
                        if current_event in ("error", "failed"):
                            raise KokoroError("Gradio queue failed: " + payload[:300])
                        if current_event == "complete":
                            try:
                                result = json.loads(payload)
                            except ValueError as exc:
                                raise KokoroError("Invalid Gradio completion data") from exc
                            return self._read_outputs(base, result, deadline)
                        current_event = ""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise KokoroError(f"Gradio queue/download failed: {exc}") from exc
        raise KokoroError("Gradio queue ended without completion")

    @staticmethod
    def _read_outputs(base, result, deadline):
        if not isinstance(result, list) or len(result) != 3:
            raise KokoroError("Gradio /synthesize must return audio, file, status")
        if not isinstance(result[2], str):
            raise KokoroError("Gradio status output is not text")
        if not isinstance(result[0], (str, dict)) or not isinstance(result[1], (str, dict)):
            raise KokoroError("Gradio audio/file outputs are invalid")
        def download_url(value):
            if isinstance(value, dict):
                url = value.get("url")
                path = value.get("path")
            else:
                url, path = None, value
            if not url and isinstance(path, str):
                url = base + "/gradio_api/file=" + urllib.parse.quote(path, safe="/")
            if not isinstance(url, str):
                raise KokoroError("Missing Gradio file URL")
            parsed = urllib.parse.urlsplit(url)
            base_parsed = urllib.parse.urlsplit(base)
            if parsed.scheme != "http" or parsed.hostname != base_parsed.hostname or parsed.port != base_parsed.port:
                raise KokoroError("Gradio file URL must use the same loopback service")
            if not parsed.path.startswith(("/gradio_api/file=", "/file=")):
                raise KokoroError("Unexpected Gradio file download URL")
            return url
        first, second = download_url(result[0]), download_url(result[1])
        if first != second:
            raise KokoroError("Gradio audio/download outputs do not reference the same file")
        data = _request(first, timeout=min(60, max(1, deadline - time.monotonic())),
                        limit=MAX_MP3)
        validate_mp3(data)
        return data


def validate_mp3(data):
    """Reject empty/truncated/non-MP3 output using MPEG frame structure."""
    if not isinstance(data, bytes) or not 128 <= len(data) <= MAX_MP3:
        raise KokoroError("Empty or oversized MP3")
    offset = 0
    if data.startswith(b"ID3") and len(data) >= 10:
        offset = 10 + ((data[6] & 127) << 21) + ((data[7] & 127) << 14) + ((data[8] & 127) << 7) + (data[9] & 127)
    for pos in range(offset, min(offset + 4096, len(data) - 4)):
        header = int.from_bytes(data[pos:pos+4], "big")
        if header >> 21 != 0x7ff:
            continue
        version = (header >> 19) & 3
        layer = (header >> 17) & 3
        bitrate_index = (header >> 12) & 15
        sample_index = (header >> 10) & 3
        if version == 1 or layer != 1 or bitrate_index in (0, 15) or sample_index == 3:
            continue
        rates = (44100, 48000, 32000)
        sample = rates[sample_index] // (1 if version == 3 else 2 if version == 2 else 4)
        bitrates = (0,32,40,48,56,64,80,96,112,128,160,192,224,256,320)
        bitrate = bitrates[bitrate_index] * 1000 if version == 3 else (0,8,16,24,32,40,48,56,64,80,96,112,128,144,160)[bitrate_index] * 1000
        frame_len = (144 if version == 3 else 72) * bitrate // sample + ((header >> 9) & 1)
        next_pos = pos + frame_len
        if frame_len > 4 and next_pos + 2 <= len(data) and data[next_pos] == 0xff and data[next_pos+1] & 0xe0 == 0xe0:
            return
    raise KokoroError("MP3 frame structure validation failed")
