import asyncio
from typing import Dict, List, Optional

import edge_tts


# Minimal language map (code -> full name) for UI display
LANGUAGE_MAP: Dict[str, str] = {
    "af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "az": "Azerbaijani",
    "bg": "Bulgarian", "bn": "Bengali", "bs": "Bosnian", "ca": "Catalan",
    "cs": "Czech", "cy": "Welsh", "da": "Danish", "de": "German",
    "el": "Greek", "en": "English", "es": "Spanish", "et": "Estonian",
    "fa": "Persian", "fi": "Finnish", "fil": "Filipino", "fr": "French",
    "ga": "Irish", "gl": "Galician", "gu": "Gujarati", "he": "Hebrew",
    "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian", "id": "Indonesian",
    "is": "Icelandic", "it": "Italian", "ja": "Japanese", "jv": "Javanese",
    "ka": "Georgian", "kk": "Kazakh", "km": "Khmer", "kn": "Kannada",
    "ko": "Korean", "lo": "Lao", "lt": "Lithuanian", "lv": "Latvian",
    "mk": "Macedonian", "ml": "Malayalam", "mn": "Mongolian", "mr": "Marathi",
    "ms": "Malay", "mt": "Maltese", "my": "Burmese", "nb": "Norwegian",
    "ne": "Nepali", "nl": "Dutch", "pa": "Punjabi", "pl": "Polish",
    "ps": "Pashto", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian",
    "si": "Sinhala", "sk": "Slovak", "sl": "Slovenian", "so": "Somali",
    "sq": "Albanian", "sr": "Serbian", "su": "Sundanese", "sv": "Swedish",
    "sw": "Swahili", "ta": "Tamil", "te": "Telugu", "th": "Thai",
    "tr": "Turkish", "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek",
    "vi": "Vietnamese", "zh": "Chinese", "zu": "Zulu",
}


def get_languages(tts_model: str) -> Dict[str, str]:
    """Return mapping like {"en": "English", ...}."""
    return LANGUAGE_MAP.copy()


def get_language_code(language_name: str) -> str:
    inv = {v: k for k, v in LANGUAGE_MAP.items()}
    return inv.get(language_name, "en")


async def _load_voices_async() -> List[dict]:
    from edge_tts import VoicesManager

    vm = await VoicesManager.create()
    return vm.voices or []


def _ensure_run(coro):
    try:
        loop = asyncio.get_running_loop()
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        return fut.result()
    except RuntimeError:
        return asyncio.run(coro)


_VOICES_CACHE: Optional[List[dict]] = None


def _get_all_voices_cached() -> List[dict]:
    global _VOICES_CACHE
    if _VOICES_CACHE is not None:
        return _VOICES_CACHE
    voices = _ensure_run(_load_voices_async())
    _VOICES_CACHE = voices
    try:
        from edge_tts import __version__ as _v
        print(f"[AINotePro][TTS] edge-tts version: {_v}, voices={len(voices)}")
    except Exception:
        print(f"[AINotePro][TTS] voices={len(voices)}")
    return voices


def get_voices(tts_model: str, language_code: str, gender: str) -> List[str]:
    """Return voice names for a given language code and gender.

    language_code: e.g., 'en', 'fr'
    gender: 'Female' or 'Male'
    """
    try:
        voices = _get_all_voices_cached()
        out: List[str] = []
        for v in voices:
            # v example keys: 'Name', 'Gender', 'Locale', ...
            loc = (v.get("Locale") or "")
            if not loc.lower().startswith((language_code or "").lower()):
                continue
            if gender and (v.get("Gender") or "").lower() != gender.lower():
                continue
            name = v.get("ShortName") or v.get("Name")
            if name:
                out.append(name)
        return sorted(set(out))
    except Exception:
        return []


async def _save_tts_async(text: str, voice: str, speed: int, volume: int, pitch: int, output_path: str) -> None:
    speed_str = f"+{speed}%" if speed >= 0 else f"{speed}%"
    volume_str = f"+{volume}%" if volume >= 0 else f"{volume}%"
    pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"

    print(f"[AINotePro][TTS] voice={voice}, len(text)={len(text)}, rate={speed_str}, volume={volume_str}, pitch={pitch_str}, out={output_path}")
    tts = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=speed_str,
        volume=volume_str,
        pitch=pitch_str,
    )
    await tts.save(output_path)


def generate_tts_audio(text: str, voice: str, speed: int, volume: int, pitch: int, output_path: str) -> None:
    """Sync wrapper that saves audio to output_path."""
    _ensure_run(_save_tts_async(text, voice, speed, volume, pitch, output_path))
