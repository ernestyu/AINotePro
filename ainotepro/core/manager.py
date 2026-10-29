from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aqt import mw

from ..config.manager import ConfigManager
from ..services.provider_factory import create_provider
from .utils import add_image_to_media_collection, add_audio_to_media_collection, get_field_content, update_field_content


@dataclass
class GenerationRequest:
    note_ids: List[int]
    source_field: str
    destination_field: str
    service_type: str  # 'text' | 'image' | 'audio'
    provider: str
    prompt: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class AIManager:
    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or ConfigManager()

    # TEXT
    def generate_text_for_field(self, req: GenerationRequest) -> int:
        provider_cfg = self.cfg.get_provider_config(req.service_type, req.provider)
        provider = create_provider(req.service_type, req.provider, provider_cfg)

        count = 0
        for nid in req.note_ids:
            note = mw.col.get_note(nid)
            if req.source_field not in note:
                continue

            src_val = (note[req.source_field] or "").strip()
            if not src_val and not (req.options or {}).get("allow_empty_source", False):
                continue

            # image-assisted text generation (vision) support
            if (req.options or {}).get("image_url"):
                content = provider.generate_with_image(
                    image_url=req.options.get("image_url"),
                    prompt=req.prompt or "",
                    config=provider_cfg,
                )
            else:
                # simple prompt templating with {Source Field}
                prompt = (req.prompt or "").replace("{Source Field}", src_val)
                content = provider.generate(prompt=prompt, config=provider_cfg)

            if content and content.strip():
                update_field_content(note, req.destination_field, content)
                count += 1

        mw.reset()
        return count

    # IMAGE
    def generate_image_for_field(self, req: GenerationRequest) -> int:
        provider_cfg = self.cfg.get_provider_config(req.service_type, req.provider)
        provider = create_provider(req.service_type, req.provider, provider_cfg)

        count = 0
        for nid in req.note_ids:
            note = mw.col.get_note(nid)
            if req.source_field not in note:
                continue
            prompt = (note[req.source_field] or "").strip()
            if not prompt:
                continue

            image_bytes = provider.generate(prompt=prompt, config=provider_cfg)
            stored = add_image_to_media_collection(image_bytes, filename_hint=f"ainotepro-{nid}.jpg")
            html = f'<div><img src="{stored}"></div>'
            update_field_content(note, req.destination_field, html)
            count += 1

        mw.reset()
        return count

    # AUDIO (legacy entry intentionally blocked: it bypassed the V2 media policy)
    def generate_audio_for_field(self, req: GenerationRequest) -> int:
        raise RuntimeError(
            "Legacy AIManager audio entry is disabled. "
            "Open the Audio tab to use the Audio V2 background/undo/provenance workflow."
        )
