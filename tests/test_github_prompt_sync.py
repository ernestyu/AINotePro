"""Network-free GitHub Contents API tests; the real API is never called."""
import base64
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ainotepro.core.prompt_bundle import make_bundle
from ainotepro.services import github_prompts as gh


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return json.dumps(self.body).encode("utf-8")


class GitHubPromptTests(unittest.TestCase):
    settings = {"repository": "user/repo", "branch": "main",
                "path": "path/prompts.json"}

    def test_validate_repository_branch_and_path(self):
        self.assertEqual(gh.validate_settings(self.settings), self.settings)
        for bad in ({"repository": "https://github.com/x/y"},
                    {"repository": "x/y", "path": "../x.json"},
                    {"repository": "x/y", "branch": "x..y"}):
            with self.assertRaises(ValueError):
                gh.validate_settings(bad)

    def test_no_redirect_to_untrusted_host(self):
        with self.assertRaisesRegex(ValueError, "redirect"):
            gh._NoRedirect().redirect_request(
                None, None, 302, "redirect", {}, "https://evil.example")

    def test_load_decodes_json_and_keeps_token_out_of_url(self):
        remote = make_bundle({"One": "text"}, {"Two": "text"})
        response = {"type": "file", "encoding": "base64", "sha": "sha123",
                    "content": base64.b64encode(
                        json.dumps(remote).encode()).decode()}
        requests = []

        def open_(req, timeout):
            requests.append(req)
            return FakeResponse(response)

        with patch.object(gh._OPENER, "open", side_effect=open_):
            self.assertEqual(gh.load_from_github(self.settings, "secret-token"),
                             remote)
        self.assertEqual(requests[0].get_header("Authorization"),
                         "Bearer secret-token")
        self.assertNotIn("secret-token", requests[0].full_url)

    def test_save_merges_both_versions_without_overwriting_remote(self):
        remote = make_bundle({"A": "remote"}, {"X": "remote"})
        local = make_bundle({"A": "local"}, {"X": "local"})
        requests = []

        def open_(req, timeout):
            if req.get_method() == "GET":
                return FakeResponse({
                    "type": "file", "encoding": "base64", "sha": "sha123",
                    "content": base64.b64encode(
                        json.dumps(remote).encode()).decode(),
                })
            requests.append(json.loads(req.data))
            return FakeResponse({"commit": {"sha": "new"}})

        with patch.object(gh._OPENER, "open", side_effect=open_):
            result = gh.save_to_github(self.settings, "secret-token", local)
        self.assertTrue(result["changed"])
        self.assertEqual(requests[0]["sha"], "sha123")
        saved = json.loads(base64.b64decode(requests[0]["content"]))
        self.assertEqual(saved["easy"], {"A": "remote", "A (1)": "local"})
        self.assertEqual(saved["advanced"], {"X": "remote", "X (1)": "local"})

    def test_ui_wiring_and_preview_safety(self):
        source = (Path(__file__).resolve().parents[1] /
                  "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        for fragment in ("Save to GitHub", "Load from GitHub",
                         "GitHubPromptSettingsDialog",
                         "def _on_import_prompt(", "def _on_export_prompt(",
                         "prompt_library_snapshot()", "merge_prompt_library(",
                         "_GITHUB_SYNC_WORKERS"):
            self.assertIn(fragment, source)
        self.assertIn("Save or discard the current prompt draft", source)


if __name__ == "__main__":
    unittest.main()
