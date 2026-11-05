"""Portable AINotePro library: saved Text prompts and Audio Profiles only.

The file does not contain Text provider configuration, API keys, selected
Profile IDs, or other machine-specific application settings.
"""
from __future__ import annotations

import copy
import json
import re
import uuid

from ..config.audio_profiles import profile_name_key, validate_audio

FORMAT = "AINotePro.library"
VERSION = 1
MODES = ("easy", "advanced")
MAX_LIBRARY_BYTES = 900_000
MAX_PROFILES = 500

# Export only fields defined in Audio Profile V1. Unknown nested properties,
# including future credentials, must never reach local JSON or GitHub.
_PROFILE_FIELDS = (
    "schema_version", "name", "provider", "source_field",
    "destination_field", "random_strategy",
)
_PROVIDER_FIELDS = {
    "edge_tts": ("language_code",),
    "kokoro_gradio": ("base_url", "language"),
}
_VOICE_FIELDS = {
    "edge_tts": ("enabled", "voice", "gender", "speed", "volume",
                 "pitch", "preview_text"),
    "kokoro_gradio": ("enabled", "voice", "accent", "locale", "gender",
                      "speed", "preview_text"),
}


def _project(record, keys, label):
    if not isinstance(record, dict):
        raise ValueError(f"Invalid {label} in Audio Profile")
    return {key: copy.deepcopy(record[key]) for key in keys if key in record}


def _mapping(raw, label):
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid {label} prompt mapping")
    names = set()
    for name, value in raw.items():
        if (not isinstance(name, str) or not name.strip()
                or len(name) > 100 or not isinstance(value, str)):
            raise ValueError(
                f"Invalid {label} prompts: names must be 1–100 characters "
                "and values must be text"
            )
        identity = profile_name_key(name)
        if identity in names:
            raise ValueError(f"Duplicate {label} prompt name (case/NFC equivalent): {name!r}")
        names.add(identity)
    return copy.deepcopy(raw)


def _profiles(raw):
    """Only export known Audio fields, then validate their complete schema."""
    if not isinstance(raw, list) or len(raw) > MAX_PROFILES:
        raise ValueError(f"Audio Profiles must be a list of at most {MAX_PROFILES} entries")
    entries = []
    ids = {}
    names = set()
    for profile in raw:
        if not isinstance(profile, dict):
            raise ValueError("Invalid Audio Profile entry")
        if "id" in profile or "profile_id" in profile:
            raise ValueError("Audio Profile IDs must not appear in library exports")
        saved = _project(profile, _PROFILE_FIELDS, "Profile")
        configs = profile.get("provider_configs")
        if not isinstance(configs, dict):
            raise ValueError("Invalid Audio Profile provider_configs")
        saved["provider_configs"] = {}
        for provider in ("edge_tts", "kokoro_gradio"):
            config = _project(configs.get(provider), _PROVIDER_FIELDS[provider], provider)
            original_voices = configs[provider].get("voices")
            if not isinstance(original_voices, list):
                raise ValueError(f"Invalid {provider} Voice list")
            config["voices"] = [
                _project(voice, _VOICE_FIELDS[provider], f"{provider} Voice")
                for voice in original_voices
            ]
            saved["provider_configs"][provider] = config
        name = saved.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Invalid Audio Profile name")
        identity = profile_name_key(name)
        if identity in names:
            raise ValueError("Duplicate Audio Profile name (case/NFC equivalent)")
        names.add(identity)
        entries.append(saved)
        ids[str(uuid.uuid4())] = saved
    if ids:
        validate_audio({
            "schema_version": 2,
            "profiles": ids,
            "last_profile_id": None,
            "migration": {"legacy_edge_v1_done": True},
        })
    return sorted(entries, key=lambda profile: (
        profile_name_key(profile["name"]), profile["name"],
    ))


def make_bundle(easy, advanced, audio_profiles):
    easy = _mapping(easy, "Easy")
    advanced = _mapping(advanced, "Advanced")
    if any(profile_name_key(name) == "default" for name in advanced):
        raise ValueError("Advanced Default is generated dynamically and cannot be saved")
    return {
        "format": FORMAT,
        "version": VERSION,
        "prompts": {"easy": easy, "advanced": advanced},
        "audio_profiles": _profiles(audio_profiles),
    }


def parse_bundle(raw):
    """Require the single unified format; development-only old formats are removed."""
    if not isinstance(raw, dict) or set(raw) != {
        "format", "version", "prompts", "audio_profiles"
    } or raw.get("format") != FORMAT or raw.get("version") != VERSION:
        raise ValueError("Unsupported AINotePro library format/version")
    prompts = raw.get("prompts")
    if not isinstance(prompts, dict) or set(prompts) != set(MODES):
        raise ValueError("Library must contain both Easy and Advanced prompts")
    return make_bundle(prompts["easy"], prompts["advanced"], raw["audio_profiles"])


def serialize_bundle(bundle, max_bytes=None):
    data = json.dumps(parse_bundle(bundle), ensure_ascii=False, indent=2,
                      sort_keys=True).encode("utf-8") + b"\n"
    if max_bytes is not None and len(data) > max_bytes:
        raise ValueError("AINotePro library exceeds GitHub's 900 KB safety limit")
    return data


def _base_name(name):
    return re.sub(r" \([1-9][0-9]*\)$", "", name)


def _candidate(base, number):
    suffix = f" ({number})"
    return base[:100 - len(suffix)] + suffix


def _same_numbered_family(name, base):
    """Recognize numbered siblings including suffixes on 100-char base names."""
    if profile_name_key(name) == profile_name_key(base):
        return True
    match = re.search(r" \(([1-9][0-9]*)\)$", name)
    return bool(match and profile_name_key(name) ==
                profile_name_key(_candidate(base, int(match.group(1)))))


def _merge_named(existing, incoming, content_equal, *, protect_default=False):
    """Return a non-destructive, idempotent union of two named collections."""
    result = copy.deepcopy(existing)
    stats = {"added": 0, "renamed": 0, "unchanged": 0}
    for item in incoming:
        proposed = item["name"]
        names = {profile_name_key(entry["name"]): entry for entry in result}
        match = names.get(profile_name_key(proposed))
        if match is not None and content_equal(match, item):
            stats["unchanged"] += 1
            continue
        base = _base_name(proposed)
        # An existing numbered sibling with the same contents means that a
        # previous import already inserted this item. Do not multiply copies.
        # Numeric siblings belong to the same name family, but unrelated
        # aliases are intentional and never deduplicated by content alone.
        if any(_same_numbered_family(entry["name"], base)
               and content_equal(entry, item) for entry in result):
            stats["unchanged"] += 1
            continue
        if match is None and (profile_name_key(proposed) != "default" or not protect_default):
            result.append(copy.deepcopy(item))
            stats["added"] += 1
            continue
        number = 1
        while True:
            candidate = _candidate(base, number)
            previous = names.get(profile_name_key(candidate))
            if previous is not None:
                if content_equal(previous, item):
                    stats["unchanged"] += 1
                    break
                number += 1
                continue
            renamed = copy.deepcopy(item)
            renamed["name"] = candidate
            result.append(renamed)
            stats["added"] += 1
            stats["renamed"] += 1
            break
    return result, stats


def merge_mode(existing, incoming, mode, *, protect_default=True):
    current = _mapping(existing, mode)
    additional = _mapping(incoming, mode)
    old = [{"name": name, "content": value} for name, value in current.items()]
    new = [{"name": name, "content": value} for name, value in additional.items()]
    result, stats = _merge_named(
        old, new, lambda a, b: a["content"] == b["content"],
        protect_default=protect_default and mode == "easy",
    )
    return {item["name"]: item["content"] for item in result}, stats


def _same_profile(a, b):
    # The display name is handled by the collision rule; all other saved
    # provider/voice/source/destination settings must match exactly.
    return {k: v for k, v in a.items() if k != "name"} == {
        k: v for k, v in b.items() if k != "name"
    }


def merge_audio_profiles(existing, incoming):
    old, new = _profiles(existing), _profiles(incoming)
    merged, stats = _merge_named(old, new, _same_profile)
    return _profiles(merged), stats


def merge_bundles(existing, incoming, *, protect_default=True):
    old, new = parse_bundle(existing), parse_bundle(incoming)
    merged = make_bundle(old["prompts"]["easy"], old["prompts"]["advanced"],
                         old["audio_profiles"])
    stats = {}
    for mode in MODES:
        merged["prompts"][mode], stats[mode] = merge_mode(
            merged["prompts"][mode], new["prompts"][mode], mode,
            protect_default=protect_default,
        )
    merged["audio_profiles"], stats["audio_profiles"] = merge_audio_profiles(
        merged["audio_profiles"], new["audio_profiles"]
    )
    return parse_bundle(merged), stats
