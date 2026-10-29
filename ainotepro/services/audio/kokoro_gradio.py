"""Loopback-only Gradio queued API adapter for local Kokoro MLX.

Transport is a development candidate pending real Anki + Gradio field validation.
The queue reader is supervised with separate queue, processing and total deadlines;
network work never runs on the Anki UI thread.
"""
from __future__ import annotations

import hashlib
import json
import queue
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

PREFIXES = ("af_", "am_", "bf_", "bm_")
MAX_MP3 = 20 * 1024 * 1024
MAX_TEXT = 6000
PROBE_SECONDS = 10
QUEUE_SECONDS = 120
PROCESS_SECONDS = 300
TOTAL_SECONDS = 420


class KokoroError(RuntimeError):
    code = "failed_synthesis"

    def __str__(self):
        return f"{self.code}: {super().__str__()}"


class KokoroDownloadError(KokoroError):
    code = "failed_download"


class KokoroValidationError(KokoroError):
    code = "failed_validation"


class KokoroQueueError(KokoroError):
    code = "failed_synthesis"


def _remaining(deadline, category=KokoroError):
    left = deadline - time.monotonic()
    if left <= 0:
        raise category("Deadline exceeded")
    return left


def _base_url(url):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost")
            or parts.username or parts.password or parts.path not in ("", "/")
            or parts.query or parts.fragment or (not parts.port and parts.netloc.endswith(":"))):
        raise KokoroValidationError("Only local loopback HTTP Gradio endpoints are permitted")
    try:
        if parts.hostname == "localhost":
            addresses = socket.getaddrinfo(parts.hostname, parts.port or 80)
            if any(addr[4][0] not in ("127.0.0.1", "::1") for addr in addresses):
                raise KokoroValidationError("localhost must resolve only to loopback")
    except OSError as exc:
        raise KokoroValidationError("Cannot resolve local Kokoro host") from exc
    return f"http://{parts.hostname}:{parts.port or 80}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise KokoroValidationError("Gradio redirect rejected")


_OPENER = urllib.request.build_opener(_NoRedirect)


def _open(url, method="GET", data=None, timeout=10, error_class=KokoroError):
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Content-Type": "application/json"} if body else {})
    try:
        return _OPENER.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise KokoroQueueError("Gradio queue rejected request (HTTP 429)") from exc
        raise error_class(f"Gradio HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise error_class(f"Gradio connection failed: {exc}") from exc


def _json(url, method="GET", data=None, deadline=None):
    timeout = min(PROBE_SECONDS, _remaining(deadline)) if deadline else PROBE_SECONDS
    with _open(url, method, data, timeout) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise KokoroValidationError("Gradio JSON response exceeds size limit")
    try:
        return json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise KokoroValidationError("Invalid Gradio JSON") from exc


def _endpoint(info):
    named = info.get("named_endpoints", {}) if isinstance(info, dict) else {}
    ep = named.get("/synthesize") or named.get("synthesize") if isinstance(named, dict) else None
    if not isinstance(ep, dict):
        raise KokoroValidationError("Expected Gradio /synthesize endpoint missing")
    params = ep.get("parameters", [])
    if not isinstance(params, list) or [p.get("parameter_name") for p in params if isinstance(p, dict)] != ["text", "voice", "speed"]:
        raise KokoroValidationError("Incompatible Gradio /synthesize parameters")
    if not isinstance(ep.get("returns"), list) or len(ep["returns"]) != 3:
        raise KokoroValidationError("Incompatible Gradio /synthesize outputs")
    return params


def _voice_choices(choices):
    names = []
    if not isinstance(choices, list):
        return names
    for entry in choices:
        # Gradio Dropdown choices may be "id" or [display_label, actual_value].
        value = entry[1] if isinstance(entry, (tuple, list)) and len(entry) == 2 else entry
        if isinstance(value, str) and re.fullmatch(r"(af|am|bf|bm)_[a-z0-9_]+", value):
            names.append(value)
    return names


def _voices(params):
    param = params[1]
    result = []
    kind = param.get("type")
    if isinstance(kind, dict):
        result += _voice_choices(kind.get("enum"))
    component = param.get("component")
    if isinstance(component, dict):
        result += _voice_choices((component.get("props") or {}).get("choices"))
    return sorted(set(result))


def _download(url, deadline):
    try:
        with _open(url, timeout=min(30, _remaining(deadline, KokoroDownloadError)),
                   error_class=KokoroDownloadError) as response:
            chunks, size = [], 0
            while True:
                _remaining(deadline, KokoroDownloadError)
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_MP3:
                    raise KokoroValidationError("MP3 exceeds size limit")
                chunks.append(chunk)
        return b"".join(chunks)
    except (OSError, TimeoutError) as exc:
        raise KokoroDownloadError(f"MP3 download interrupted: {exc}") from exc


def _file_url(base, value):
    if isinstance(value, dict):
        url = value.get("url")
        path = value.get("path")
    else:
        url, path = None, value
    if not url and isinstance(path, str):
        url = "/gradio_api/file=" + urllib.parse.quote(path, safe="/")
    if not isinstance(url, str):
        raise KokoroValidationError("Gradio file result has no URL/path")
    if url.startswith("/"):
        url = base + url
    parsed = urllib.parse.urlsplit(url)
    origin = urllib.parse.urlsplit(base)
    if (parsed.scheme != "http" or parsed.hostname != origin.hostname
            or parsed.port != origin.port or parsed.username or parsed.password
            or not parsed.path.startswith(("/gradio_api/file=", "/file="))):
        raise KokoroValidationError("Unexpected or nonlocal Gradio download URL")
    return url


def _consume_events(response, total_deadline):
    """Supervise SSE without trusting a single blocking socket read timeout."""
    events = queue.Queue()
    stop = threading.Event()

    def reader():
        event_name, data = "", []
        try:
            for raw in response:
                if stop.is_set():
                    return
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data.append(line[5:].strip())
                elif not line:
                    if data:
                        events.put((event_name, "\n".join(data)))
                    event_name, data = "", []
            events.put(("eof", ""))
        except Exception as exc:
            events.put(("error", str(exc)))

    thread = threading.Thread(target=reader, daemon=True, name="AINotePro-Kokoro-SSE")
    thread.start()
    queued_until = min(total_deadline, time.monotonic() + QUEUE_SECONDS)
    processing_until = None
    try:
        while True:
            now = time.monotonic()
            stage_deadline = queued_until if processing_until is None else processing_until
            if now >= min(total_deadline, stage_deadline):
                stage = "queue" if processing_until is None else "synthesis"
                raise KokoroQueueError(f"Kokoro {stage} deadline exceeded")
            try:
                event, payload = events.get(timeout=min(1.0, total_deadline - now, stage_deadline - now))
            except queue.Empty:
                continue
            if event in ("generating", "processing", "started") and processing_until is None:
                processing_until = min(total_deadline, time.monotonic() + PROCESS_SECONDS)
            elif event == "complete":
                try:
                    return json.loads(payload)
                except (UnicodeError, ValueError) as exc:
                    raise KokoroValidationError("Invalid Gradio completion JSON") from exc
            elif event in ("error", "failed", "eof"):
                raise KokoroQueueError(f"Gradio queue ended: {payload[:250]}")
            # "heartbeat", "queued", and unknown informational events are ignored.
    finally:
        stop.set()
        try:
            response.close()
        except OSError:
            pass


class KokoroGradioProvider:
    def probe(self, config):
        base = _base_url(config.get("base_url", "http://127.0.0.1:7860"))
        deadline = time.monotonic() + PROBE_SECONDS
        try:
            info = _json(base + "/gradio_api/info", deadline=deadline)
        except KokoroError:
            info = _json(base + "/info", deadline=deadline)
        params = _endpoint(info)
        voices = _voices(params)
        if not voices:
            cfg = _json(base + "/config", deadline=deadline)
            for comp in cfg.get("components", []):
                props = comp.get("props") or {}
                if str(comp.get("type", "")).lower() == "dropdown" or props.get("choices"):
                    voices.extend(_voice_choices(props.get("choices")))
        voices = sorted(set(voices))
        if not voices:
            raise KokoroValidationError("No valid English voices exposed by Gradio")
        return voices

    def generate(self, text, config):
        text = str(text or "").strip()
        voice = str(config.get("voice", ""))
        try:
            speed = float(config.get("speed", 1.0))
        except (TypeError, ValueError) as exc:
            raise KokoroValidationError("Invalid Kokoro speed") from exc
        if not text or len(text) > MAX_TEXT:
            raise KokoroValidationError("Kokoro text must contain 1–6000 characters")
        if not re.fullmatch(r"(af|am|bf|bm)_[a-z0-9_]+", voice) or not 0.7 <= speed <= 1.3:
            raise KokoroValidationError("Invalid Kokoro voice/speed")
        base = _base_url(config.get("base_url", "http://127.0.0.1:7860"))
        deadline = time.monotonic() + TOTAL_SECONDS
        event = _json(base + "/gradio_api/call/synthesize", method="POST",
                      data={"data": [text, voice, speed]}, deadline=deadline)
        event_id = event.get("event_id") if isinstance(event, dict) else None
        if not isinstance(event_id, str) or not re.fullmatch(r"[\w-]{1,128}", event_id):
            raise KokoroQueueError("Gradio queue returned no valid event_id")
        url = base + "/gradio_api/call/synthesize/" + urllib.parse.quote(event_id)
        with _open(url, timeout=min(PROCESS_SECONDS, _remaining(deadline)),
                   error_class=KokoroQueueError) as response:
            result = _consume_events(response, deadline)
        return self._read_outputs(base, result, deadline)

    @staticmethod
    def _read_outputs(base, result, deadline):
        if not isinstance(result, list) or len(result) != 3:
            raise KokoroValidationError("Gradio /synthesize must return three outputs")
        if not isinstance(result[2], str):
            raise KokoroValidationError("Gradio status output is not text")
        if not isinstance(result[0], (str, dict)) or not isinstance(result[1], (str, dict)):
            raise KokoroValidationError("Gradio audio/file output types are invalid")
        first = _file_url(base, result[0])
        second = _file_url(base, result[1])
        data = _download(first, deadline)
        validate_mp3(data)
        # The second output is a separate contract: verify it is accessible and
        # consistent even when Gradio assigns a distinct cache URL.
        if first != second:
            alternate = _download(second, deadline)
            if hashlib.sha256(alternate).digest() != hashlib.sha256(data).digest():
                raise KokoroValidationError("Gradio audio and download outputs differ")
        return data


def validate_mp3(data):
    """Reject empty/truncated/non-MP3 output using MPEG frame structure."""
    if not isinstance(data, bytes) or not 128 <= len(data) <= MAX_MP3:
        raise KokoroValidationError("Empty or oversized MP3")
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
    raise KokoroValidationError("MP3 frame structure validation failed")
