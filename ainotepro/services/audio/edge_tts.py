from __future__ import annotations

from typing import Dict
import os

from ...gen_audio.models.edge_tts.tts_handler import generate_tts_audio


class EdgeTTSProvider:
    def generate(self, text: str, config: Dict) -> bytes:
        # Use the existing async routine, but wait synchronously for completion by running event loop.
        # We generate to a temp file then read back into bytes for unified interface.
        import asyncio
        import tempfile

        voice = (config or {}).get("voice", "en-US-AriaNeural")
        speed = int((config or {}).get("speed", 0))
        volume = int((config or {}).get("volume", 0))
        pitch = int((config or {}).get("pitch", 0))

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            tmp_path = tf.name

        async def _run():
            await generate_tts_audio(text, voice, speed, volume, pitch, tmp_path)

        try:
            try:
                loop = asyncio.get_running_loop()
                # If there is a running loop (inside Anki), schedule and wait
                fut = asyncio.run_coroutine_threadsafe(_run(), loop)
                fut.result()
            except RuntimeError:
                asyncio.run(_run())

            with open(tmp_path, "rb") as f:
                data = f.read()
            return data
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

