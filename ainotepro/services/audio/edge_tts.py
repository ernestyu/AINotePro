from __future__ import annotations

from typing import Dict
import os

from ...gen_audio.models.edge_tts.tts_handler import generate_tts_audio


class EdgeTTSProvider:
    def generate(self, text: str, config: Dict) -> bytes:
        # Generate to a temp file synchronously, then read bytes.
        import tempfile

        voice = (config or {}).get("voice", "en-US-AriaNeural")
        speed = int((config or {}).get("speed", 0))
        volume = int((config or {}).get("volume", 0))
        pitch = int((config or {}).get("pitch", 0))

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            tmp_path = tf.name

        print(f"[AINotePro][TTS Provider] begin voice={voice} speed={speed} volume={volume} pitch={pitch} path={tmp_path}")
        try:
            generate_tts_audio(text, voice, speed, volume, pitch, tmp_path)
            size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
            print(f"[AINotePro][TTS Provider] file_ready size={size}")
            with open(tmp_path, "rb") as f:
                data = f.read()
            return data
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

