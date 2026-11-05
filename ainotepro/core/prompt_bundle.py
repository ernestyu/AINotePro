"""Portable AINotePro library: saved Text prompts and Audio Profiles only.

The file does not contain Text provider configuration, API keys, selected
Profile IDs, or other machine-specific application settings.
"""
from __future__ import annotations

import copy
import json
import re
import uuid

from ..config.audio_profiles import validate_audio

FORMAT = "AINotePro.library"
VERSION = 1
MODES = ("easy", "advanced")
MAX_LIBRARY_BYTES = 900_000
MAX_PROFILES = 500


def _mapping(raw, label):
    if not isinstance(raw, dict) or any(
        not isinstance(name, str) or not name.strip() or len(name) > 100
        or not isinstance(value, str) for name, value in raw.items()
    ):
        raise ValueError(f"Invalid {label} prompts: names must be 1–100 characters and values must be text")
    return copy.deepcopy(raw)


def _profiles(raw):
    """Validate full four-Voice profiles without consulting live TTS services."""
    if not isinstance(raw, list) or len(raw) > MAX_PROFILES:
        raise ValueError(f"Audio Profiles must be a list of at most {MAX_PROFILES} entries")
    entries = copy.deepcopy(raw)
    ids = {}
    for profile in entries:
        if not isinstance(profile, dict):
            raise ValueError("Invalid Audio Profile entry")
        # The library transports profiles, not the local UUIDs of their owner.
        if "id" in profile or "profile_id" in profile:
            raise ValueError("Audio Profile IDs must not appear in library exports")
        ids[str(uuid.uuid4())] = profile
    if ids:
        validate_audio({
            "schema_version": 2,
            "profiles": ids,
            "last_profile_id": None,
            "migration": {"legacy_edge_v1_done": True},
        })
    return sorted(entries, key=lambda profile: (profile["name"].casefold(), profile["name"]))


def make_bundle(easy, advanced, audio_profiles):
    easy = _mapping(easy, "Easy")
    advanced = _mapping(advanced, "Advanced")
    if "Default" in advanced:
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


def _merge_named(existing, incoming, content_equal, *, protect_default=False):
    """Return a non-destructive, idempotent union of two named collections."""
    result = copy.deepcopy(existing)
    stats = {"added": 0, "renamed": 0, "unchanged": 0}
    for item in incoming:
        proposed = item["name"]
        names = {entry["name"].casefold(): entry for entry in result}
        match = names.get(proposed.casefold())
        if match is not None and content_equal(match, item):
            stats["unchanged"] += 1
            continue
        base = _base_name(proposed)
        # An existing numbered sibling with the same contents means that a
        # previous import already inserted this item. Do not multiply copies.
        family = re.compile(r"^" + re.escape(base) + r"(?: \([1-9][0-9]*\))?$", re.I)
        if any(family.fullmatch(entry["name"]) and content_equal(entry, item)
               for entry in result):
            stats["unchanged"] += 1
            continue
        if match is None and (proposed.casefold() != "default" or not protect_default):
            result.append(copy.deepcopy(item))
            stats["added"] += 1
            continue
        number = 1
        while True:
            candidate = _candidate(base, number)
            previous = names.get(candidate.casefold())
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
