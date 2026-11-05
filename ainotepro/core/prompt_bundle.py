"""Portable Easy/Advanced prompt library and non-destructive name collision rules."""
from __future__ import annotations

import json
import re

FORMAT = "AINotePro.prompt-library"
VERSION = 2
MODES = ("easy", "advanced")
MAX_LIBRARY_BYTES = 900_000


def _mapping(raw, label):
    if not isinstance(raw, dict) or any(
        not isinstance(name, str) or not name.strip() or len(name) > 100
        or not isinstance(value, str) for name, value in raw.items()
    ):
        raise ValueError(f"Invalid {label} prompt mapping; names must be 1–100 characters and values must be text")
    return dict(raw)


def make_bundle(easy, advanced):
    return {"format": FORMAT, "version": VERSION,
            "easy": _mapping(easy, "Easy"), "advanced": _mapping(advanced, "Advanced")}


def parse_bundle(raw):
    """Read a complete V2 library or an earlier single-mode/legacy export."""
    if not isinstance(raw, dict):
        raise ValueError("Expected a JSON object for the prompt library")
    if raw.get("format") == FORMAT and raw.get("version") == VERSION:
        if set(raw) != {"format", "version", "easy", "advanced"}:
            raise ValueError("Invalid prompt library keys")
        return make_bundle(raw["easy"], raw["advanced"])
    if "mode" in raw or "prompts" in raw:
        if raw.get("version") != 1 or raw.get("mode") not in MODES:
            raise ValueError("Unsupported legacy prompt export")
        mode = raw["mode"]
        return make_bundle(raw["prompts"] if mode == "easy" else {},
                           raw["prompts"] if mode == "advanced" else {})
    if any(k in raw for k in ("format", "version", "easy", "advanced")):
        raise ValueError("Unsupported prompt library format/version")
    return make_bundle(raw, {})


def serialize_bundle(bundle, max_bytes=None):
    data = json.dumps(parse_bundle(bundle), ensure_ascii=False, indent=2,
                      sort_keys=True).encode("utf-8") + b"\n"
    if max_bytes is not None and len(data) > max_bytes:
        raise ValueError("Prompt library exceeds GitHub's 900 KB safety limit")
    return data


def merge_mode(existing, incoming, mode, *, protect_default=True):
    """Never replace stored content; conflicting names acquire numeric suffixes."""
    result = _mapping(existing, mode)
    addition = _mapping(incoming, mode)
    stats = {"added": 0, "renamed": 0, "unchanged": 0}
    for proposed, content in addition.items():
        names = {name.casefold(): name for name in result}
        match = names.get(proposed.casefold())
        if match is not None and result[match] == content:
            stats["unchanged"] += 1
            continue
        # Protect the built-in or dynamically generated Default entry.
        if match is None and (proposed != "Default" or not protect_default):
            result[proposed] = content
            stats["added"] += 1
            continue
        base = re.sub(r" \([1-9][0-9]*\)$", "", proposed)
        family = re.compile(r"^" + re.escape(base) + r"(?: \([1-9][0-9]*\))?$", re.I)
        if any(family.fullmatch(name) and text == content for name, text in result.items()):
            stats["unchanged"] += 1
            continue
        counter = 1
        while True:
            suffix = f" ({counter})"
            candidate = base[:100 - len(suffix)] + suffix
            if candidate.casefold() not in names:
                result[candidate] = content
                stats["added"] += 1
                stats["renamed"] += 1
                break
            counter += 1
    return result, stats


def merge_bundles(existing, incoming, *, protect_default=True):
    old, new = parse_bundle(existing), parse_bundle(incoming)
    merged = make_bundle(old["easy"], old["advanced"])
    stats = {}
    for mode in MODES:
        merged[mode], stats[mode] = merge_mode(merged[mode], new[mode], mode, protect_default=protect_default)
    return merged, stats
