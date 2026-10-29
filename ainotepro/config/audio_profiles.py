"""Versioned Audio V2 profiles; never merge the profiles mapping with defaults."""
from __future__ import annotations

import copy
import re
import uuid

DEFAULT_URL = "http://127.0.0.1:7860"
PROFILE_VERSION = 2
ID_RE = re.compile(r"^(legacy-edge-default|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")
KOKORO_RE = re.compile(r"^(af|am|bf|bm)_[a-z0-9_]+$")


def _edge_voice(enabled=False, voice="", gender="Female", speed=0, volume=0, pitch=0, preview_text=""):
    return dict(enabled=bool(enabled), voice=voice, gender=gender, speed=int(speed),
                volume=int(volume), pitch=int(pitch), preview_text=preview_text)


def _kokoro_voice(enabled=False, voice="", accent="American", gender="Female", speed=1.0,
                  preview_text="", locale=None):
    return dict(enabled=bool(enabled), voice=voice, accent=accent,
                locale=locale or ("en-GB" if accent == "British" else "en-US"),
                gender=gender, speed=float(speed), preview_text=preview_text)


def default_profile(name="English", provider="edge_tts"):
    return {
        "schema_version": 2, "name": name, "provider": provider,
        "source_field": "", "destination_field": "", "random_strategy": "uniform_per_note",
        "provider_configs": {
            "edge_tts": {"language_code": "en", "voices": [
                _edge_voice(False, "en-US-AriaNeural"),
                _edge_voice(), _edge_voice()]},
            "kokoro_gradio": {"base_url": DEFAULT_URL, "language": "en", "voices": [
                _kokoro_voice(False, "af_heart"),
                _kokoro_voice(False, "bf_emma", "British"),
                _kokoro_voice(False, "am_michael", gender="Male")]},
        },
    }


def migrate_audio(audio):
    """Migrate legacy Edge once; never recreate a previously deleted profile."""
    audio = copy.deepcopy(audio or {})
    if "profiles" in audio or audio.get("migration", {}).get("legacy_edge_v1_done"):
        validate_audio(audio)
        return audio
    legacy = audio.get("edge_tts") or {}
    profile = default_profile("Imported Edge TTS")
    ecfg = profile["provider_configs"]["edge_tts"]
    ecfg["language_code"] = legacy.get("language_code") or "en"
    if isinstance(legacy.get("voices"), list):
        for i, voice in enumerate(legacy["voices"][:3]):
            if isinstance(voice, dict):
                ecfg["voices"][i].update({k: voice[k] for k in ecfg["voices"][i] if k in voice})
    else:
        ecfg["voices"][0].update({k: legacy[k] for k in ("voice", "speed", "volume", "pitch") if k in legacy})
        ecfg["voices"][0]["enabled"] = bool(legacy.get("voice"))
    audio.update(schema_version=2, profiles={"legacy-edge-default": profile},
                 last_profile_id="legacy-edge-default", migration={"legacy_edge_v1_done": True})
    validate_audio(audio)
    return audio


def validate_audio(audio):
    """Structural and semantic validation independent of live provider availability."""
    if not isinstance(audio, dict) or audio.get("schema_version") != 2:
        raise ValueError("Unsupported Audio profile schema_version")
    profiles = audio.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("Audio profiles missing or empty")
    if audio.get("last_profile_id") is not None and audio["last_profile_id"] not in profiles:
        raise ValueError("last_profile_id does not reference a profile")
    if audio.get("migration", {}).get("legacy_edge_v1_done") is not True:
        raise ValueError("Audio migration marker missing")
    names = set()
    for pid, profile in profiles.items():
        if not ID_RE.fullmatch(pid):
            raise ValueError("Invalid Profile ID")
        if not isinstance(profile, dict) or profile.get("schema_version") != 2:
            raise ValueError("Invalid Profile version")
        name = str(profile.get("name", "")).strip()
        if not name or len(name) > 100 or name.casefold() in names:
            raise ValueError("Invalid or duplicate Profile name")
        names.add(name.casefold())
        if profile.get("provider") not in ("edge_tts", "kokoro_gradio"):
            raise ValueError("Invalid Audio provider")
        if profile.get("random_strategy") != "uniform_per_note":
            raise ValueError("Unsupported random strategy")
        if not isinstance(profile.get("source_field"), str) or not isinstance(profile.get("destination_field"), str):
            raise ValueError("Invalid field name")
        configs = profile.get("provider_configs")
        if not isinstance(configs, dict) or set(("edge_tts", "kokoro_gradio")) - set(configs):
            raise ValueError("Missing provider configurations")
        edge, kokoro = configs["edge_tts"], configs["kokoro_gradio"]
        if not isinstance(edge.get("language_code"), str) or not edge["language_code"]:
            raise ValueError("Invalid Edge language")
        if kokoro.get("language") != "en":
            raise ValueError("Kokoro is English-only")
        from urllib.parse import urlsplit
        url = urlsplit(kokoro.get("base_url", ""))
        if url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1") or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
            raise ValueError("Kokoro URL must be local loopback HTTP")
        for provider, config in (("edge_tts", edge), ("kokoro_gradio", kokoro)):
            voices = config.get("voices")
            if not isinstance(voices, list) or len(voices) != 3:
                raise ValueError("Exactly three Voice blocks are required")
            for v in voices:
                if not isinstance(v, dict) or not isinstance(v.get("enabled"), bool):
                    raise ValueError("Invalid Voice block")
                if v.get("gender") not in ("Female", "Male") or not isinstance(v.get("voice"), str):
                    raise ValueError("Invalid Voice gender/ID")
                if not isinstance(v.get("preview_text"), str):
                    raise ValueError("Invalid preview text")
                if provider == "edge_tts":
                    for field in ("speed", "volume", "pitch"):
                        if type(v.get(field)) is not int or not -50 <= v[field] <= 50:
                            raise ValueError("Invalid Edge slider value")
                else:
                    if v.get("accent") not in ("American", "British"):
                        raise ValueError("Invalid Kokoro accent")
                    locale = v.get("locale", "en-GB" if v["accent"] == "British" else "en-US")
                    if locale not in ("en-US", "en-GB") or locale != ("en-GB" if v["accent"] == "British" else "en-US"):
                        raise ValueError("Kokoro locale/accent mismatch")
                    if type(v.get("speed")) not in (int, float) or not 0.7 <= v["speed"] <= 1.3:
                        raise ValueError("Invalid Kokoro speed")
                    voice = v["voice"]
                    if voice:
                        match = KOKORO_RE.fullmatch(voice)
                        if not match:
                            raise ValueError("Invalid Kokoro voice ID")
                        prefix = match.group(1)
                        if ("British" if prefix[0] == "b" else "American") != v["accent"] or ("Female" if prefix[1] == "f" else "Male") != v["gender"]:
                            raise ValueError("Kokoro voice/accent/gender mismatch")
                    elif v["enabled"]:
                        raise ValueError("Enabled Voice has no ID")
    return audio


def new_profile_id():
    return str(uuid.uuid4())
