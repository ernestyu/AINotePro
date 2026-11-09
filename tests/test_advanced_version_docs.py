"""Version and user-facing documentation contracts for the release candidate."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from ainotepro.version import addon_version

ROOT = Path(__file__).resolve().parents[1]


class VersionDocumentationTests(unittest.TestCase):
    def test_window_version_comes_from_manifest(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(addon_version(), manifest["version"])
        self.assertEqual(manifest["version"], "1.1.1")  # No premature release bump.
        source = (ROOT / "ainotepro/ainotepro_gui.py").read_text(encoding="utf-8")
        self.assertIn('v{addon_version()}', source)
        self.assertNotIn('AINotePro — v1.0.0', source)

    def test_bilingual_batch_size_and_no_resolve_control(self):
        for path in ("README.md", "README.zh-CN.md"):
            text = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("1–10", text)
            self.assertIn("1–99", text)
            self.assertIn("default 1" if path == "README.md" else "默认 1", text)
            self.assertNotIn("11–99", text)
            if path == "README.zh-CN.md":
                self.assertIn("Resolve", text)
            self.assertEqual(text.count("user_files/logs/github_sync.log"), 1)


if __name__ == "__main__":
    unittest.main()
