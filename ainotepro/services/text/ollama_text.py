from __future__ import annotations

import json
import requests
from typing import Dict

from ..base import TextProvider


class OllamaTextProvider(TextProvider):
    def _base(self, config: Dict) -> str:
        return (config or {}).get("base_url", "http://localhost:11434").rstrip("/")

    def generate(self, prompt: str, config: Dict) -> str:
        # Use Ollama's native /api/chat endpoint (non-stream) and parse message.content
        url = f"{self._base(config)}/api/chat"
        body = {
            "model": (config or {}).get("model") or "llama3",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": (config or {}).get("temperature", 0.7)},
        }
        print(f"[AINotePro] POST {url}")
        try:
            import json as _json
            first_msg = body.get("messages", [{}])[0].get("content", "")
            preview = (first_msg[:200] + "…") if len(first_msg) > 200 else first_msg
            print("[AINotePro] body:", _json.dumps({
                "model": body.get("model"),
                "messages": len(body.get("messages", [])),
                "stream": body.get("stream"),
                "content_preview": preview,
            }, ensure_ascii=False))
        except Exception:
            pass

        timeout = int((config or {}).get("timeout", 300))
        r = requests.post(url, json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json() or {}
        msg = (data.get("message") or {}).get("content", "")
        return _remove_think((msg or "").strip())

    def list_models(self, config: Dict) -> list[str]:
        # Ollama tags endpoint
        url = f"{self._base(config)}/api/tags"
        print(f"[AINotePro] GET {url}")
        try:
            r = requests.get(url, timeout=int((config or {}).get("timeout", 30)))
            r.raise_for_status()
            data = r.json() or {}
            models = data.get("models", [])
            names = []
            for m in models:
                # Support either 'name' or 'model' key variations
                n = m.get("name") or m.get("model") or ""
                if n:
                    names.append(n)
            names = sorted(set(names))
            return names
        except Exception:
            return []

    def generate_batch(self, inputs: list[str], config: Dict) -> list[str]:
        # Ollama does not provide a true multi-input batch endpoint that returns
        # an array mapped to inputs. Perform sequential generation here, but make
        # sure to apply the instruction (Prompt Preview) by replacing {Source Field}
        # for each input. This guarantees prompts are honored.
        instruction = (config or {}).get("instruction", "")
        total = len(inputs)
        print(f"[AINotePro][Batch] Ollama: sequential per-item, items={total}")
        results: list[str] = []
        for i, s in enumerate(inputs, 1):
            prompt = instruction.replace("{Source Field}", s)
            # Log both the raw input and prompt preview so issues are easy to spot
            ip = (s[:120] + "…") if len(s) > 120 else s
            pp = (prompt[:200] + "…") if len(prompt) > 200 else prompt
            try:
                print(f"[AINotePro][Ollama Seq] {i}/{total} input=\"{ip}\" prompt_preview=\"{pp}\"")
            except Exception:
                pass
            try:
                results.append(self.generate(prompt, config))
            except Exception as e:
                results.append(f"[Error] {e}")
        return results


def _remove_think(s: str) -> str:
    import re

    return re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()

