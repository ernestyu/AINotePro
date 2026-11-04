"""Headless tests for four Audio voices and safe upgrades from three-slot profiles."""
from __future__ import annotations

import ast
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path

from ainotepro.config.audio_profiles import VOICE_SLOTS, default_profile, migrate_audio, validate_audio
from ainotepro.config import manager


class FourVoiceTests(unittest.TestCase):
    def old_audio(self):
        audio = migrate_audio({"edge_tts": {"voice": "en-US-AriaNeural"}})
        profile = audio["profiles"]["legacy-edge-default"]
        for provider in ("edge_tts", "kokoro_gradio"):
            profile["provider_configs"][provider]["voices"].pop()
        return audio

    def test_new_profiles_have_four_independent_disabled_extra_slots(self):
        profile = default_profile()
        for cfg in profile["provider_configs"].values():
            self.assertEqual(len(cfg["voices"]), VOICE_SLOTS)
            self.assertFalse(cfg["voices"][3]["enabled"])
            self.assertEqual(cfg["voices"][3]["voice"], "")

    def test_upgrade_preserves_all_existing_voice_settings(self):
        old = self.old_audio()
        profile = old["profiles"]["legacy-edge-default"]
        profile["provider_configs"]["edge_tts"]["voices"][2]["preview_text"] = "Keep me"
        original = copy.deepcopy(old)
        upgraded = migrate_audio(old)
        validate_audio(upgraded)
        self.assertEqual(old, original)  # Input is not mutated.
        for provider in ("edge_tts", "kokoro_gradio"):
            before = original["profiles"]["legacy-edge-default"]["provider_configs"][provider]["voices"]
            after = upgraded["profiles"]["legacy-edge-default"]["provider_configs"][provider]["voices"]
            self.assertEqual(before, after[:3])
            self.assertEqual(len(after), 4)
            self.assertFalse(after[3]["enabled"])
            self.assertEqual(after[3]["voice"], "")
        self.assertEqual(migrate_audio(upgraded), upgraded)  # Idempotent.

    def test_invalid_slot_count_still_rejected(self):
        audio = self.old_audio()
        with self.assertRaisesRegex(ValueError, "Exactly 4 Voice"):
            validate_audio(audio)
        audio["profiles"]["legacy-edge-default"]["provider_configs"]["edge_tts"]["voices"].pop()
        with self.assertRaises(ValueError):
            migrate_audio(audio)  # Never silently accept two slots.

    def test_manager_upgrades_disk_once_and_keeps_other_settings(self):
        old_paths = (manager.USER_FILES_DIR, manager.LEGACY_USER_DATA_DIR, manager.CONFIG_FILE)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                manager.USER_FILES_DIR = tmp
                manager.LEGACY_USER_DATA_DIR = str(Path(tmp) / "nonexistent-legacy")
                manager.CONFIG_FILE = str(Path(tmp) / "user_config.json")
                raw = manager._get_default_config()
                raw["audio"] = self.old_audio()
                raw["text"]["prompts"] = {"User Prompt": "Keep"}
                Path(manager.CONFIG_FILE).write_text(json.dumps(raw), encoding="utf-8")
                cfg = manager.ConfigManager()
                first = Path(manager.CONFIG_FILE).read_bytes()
                self.assertEqual(len(cfg.get_audio()["profiles"]["legacy-edge-default"]
                                     ["provider_configs"]["edge_tts"]["voices"]), 4)
                self.assertEqual(json.loads(first)["text"]["prompts"]["User Prompt"], "Keep")
                manager.ConfigManager()
                self.assertEqual(Path(manager.CONFIG_FILE).read_bytes(), first)
            finally:
                (manager.USER_FILES_DIR, manager.LEGACY_USER_DATA_DIR,
                 manager.CONFIG_FILE) = old_paths

    def test_selector_can_choose_any_of_four_complete_blocks(self):
        path = Path(__file__).resolve().parents[1] / "ainotepro" / "ui" / "tts_tab.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        func = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "_select_voice")
        namespace = {"copy": copy, "random": random}
        module = ast.Module(body=[func], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
        select = namespace["_select_voice"]
        voices = [dict(voice=f"voice-{i}", enabled=True, speed=i) for i in range(4)]
        self.assertEqual(select(voices, chooser=lambda candidates: candidates[-1])["speed"], 3)
        rnd = random.Random(42)
        counts = {v["voice"]: 0 for v in voices}
        for _ in range(4000):
            counts[select(voices, chooser=rnd.choice)["voice"]] += 1
        self.assertTrue(all(800 < count < 1200 for count in counts.values()), counts)
        voices[3]["enabled"] = False
        self.assertNotEqual(select(voices, chooser=lambda candidates: candidates[-1])["voice"],
                            "voice-3")

    def test_ui_keeps_voice_rows_compact_with_even_intergroup_spacing(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro" / "ui" /
                  "tts_tab.py").read_text(encoding="utf-8")
        self.assertIn("for index in range(VOICE_SLOTS):", source)
        self.assertNotIn("vb.addStretch(1)", source)
        self.assertIn("vb.setSpacing(3)", source)
        self.assertIn("root.addWidget(box)\n            root.addStretch(1)", source)
        self.assertEqual(source.count("root.addStretch(1)"), 1)
        self.assertLess(source.index("vb.addLayout(row)"), source.index("vb.addLayout(params)"))
        self.assertLess(source.index("root.addWidget(box)"), source.index("root.addWidget(separator)"))

    def test_field_separator_and_bottom_profile_order(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro" / "ui" /
                  "tts_tab.py").read_text(encoding="utf-8")
        self.assertIn("separator.setFrameShape(QFrame.Shape.HLine)", source)
        self.assertIn("separator.setFrameShadow(QFrame.Shadow.Sunken)", source)
        self.assertLess(source.index("root.addWidget(separator)"),
                        source.index("root.addLayout(fields)"))
        self.assertLess(source.index("root.addLayout(fields)"),
                        source.index("root.addLayout(profile_row)"))
        main = (Path(__file__).resolve().parents[1] / "ainotepro" /
                "ainotepro_gui.py").read_text(encoding="utf-8")
        self.assertIn("self.resize(1000, 700)", main)
        self.assertIn("self.setMinimumSize(870, 700)", main)


if __name__ == "__main__":
    unittest.main()
