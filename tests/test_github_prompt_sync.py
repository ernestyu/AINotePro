"""Offline GitHub library synchronization tests using a mocked HTTPS response."""
import base64
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ainotepro.config.audio_profiles import default_profile
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


def bundle(value):
    profile = default_profile("English")
    profile["provider_configs"]["edge_tts"]["voices"][0]["speed"] = value
    return make_bundle({"A": f"prompt {value}"}, {"X": f"advanced {value}"},
                       [profile])


def remote_document(library):
    return {
        "type": "file", "encoding": "base64", "sha": "sha123",
        "content": base64.b64encode(json.dumps(library).encode()).decode(),
    }


class GitHubLibraryTests(unittest.TestCase):
    settings = {"repository": "user/repo", "branch": "main",
                "path": "ainotepro-library.json"}

    def test_validate_repository_branch_and_path(self):
        self.assertEqual(gh.validate_settings(self.settings), self.settings)
        for invalid in (
            {"repository": "https://github.com/x/y"},
            {"repository": "x/y", "path": "../x.json"},
            {"repository": "x/y", "branch": "x..y"},
        ):
            with self.assertRaises(ValueError):
                gh.validate_settings(invalid)

    def test_no_redirect_to_untrusted_host(self):
        with self.assertRaisesRegex(ValueError, "redirect"):
            gh._NoRedirect().redirect_request(
                None, None, 302, "redirect", {}, "https://evil.example")

    def test_load_reads_complete_library_without_put(self):
        remote = bundle(3)
        requests = []

        def open_(req, timeout):
            requests.append(req)
            return FakeResponse(remote_document(remote))

        with patch.object(gh._OPENER, "open", side_effect=open_):
            self.assertEqual(gh.load_from_github(self.settings, "secret-token"),
                             remote)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].get_method(), "GET")
        self.assertEqual(requests[0].get_header("Authorization"),
                         "Bearer secret-token")
        self.assertNotIn("secret-token", requests[0].full_url)

    def test_save_merges_three_domains_and_uses_sha(self):
        remote = bundle(3)
        local = bundle(7)
        writes = []

        def open_(req, timeout):
            if req.get_method() == "GET":
                return FakeResponse(remote_document(remote))
            writes.append(json.loads(req.data))
            return FakeResponse({"commit": {"sha": "new"}})

        with patch.object(gh._OPENER, "open", side_effect=open_):
            result = gh.save_to_github(self.settings, "secret-token", local)
        self.assertTrue(result["changed"])
        self.assertEqual(writes[0]["sha"], "sha123")
        saved = json.loads(base64.b64decode(writes[0]["content"]))
        self.assertEqual(saved["format"], "AINotePro.library")
        self.assertEqual(saved["prompts"]["easy"],
                         {"A": "prompt 3", "A (1)": "prompt 7"})
        self.assertEqual(saved["prompts"]["advanced"],
                         {"X": "advanced 3", "X (1)": "advanced 7"})
        self.assertEqual([p["name"] for p in saved["audio_profiles"]],
                         ["English", "English (1)"])
        self.assertEqual(saved["audio_profiles"][1]
                         ["provider_configs"]["edge_tts"]["voices"][0]["speed"], 7)

    def test_first_github_save_creates_unified_json_file(self):
        import urllib.error

        local = bundle(7)
        writes = []

        def open_(req, timeout):
            if req.get_method() == "GET":
                raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
            writes.append(json.loads(req.data))
            return FakeResponse({"commit": {"sha": "first"}})

        with patch.object(gh._OPENER, "open", side_effect=open_):
            result = gh.save_to_github(self.settings, "secret-token", local)
        self.assertTrue(result["changed"])
        self.assertNotIn("sha", writes[0])  # New file, no previous SHA.
        saved = json.loads(base64.b64decode(writes[0]["content"]))
        self.assertEqual(saved, local)

    def test_unreleased_prompt_only_remote_is_rejected(self):
        response = remote_document({
            "format": "AINotePro.prompt-library", "version": 2,
            "easy": {}, "advanced": {},
        })
        with patch.object(gh._OPENER, "open", return_value=FakeResponse(response)):
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                gh.load_from_github(self.settings, "")

    def test_ui_wiring_and_audio_refresh_contract(self):
        source = (Path(__file__).resolve().parents[1] /
                  "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        audio = (Path(__file__).resolve().parents[1] /
                 "ainotepro/ui/tts_tab.py").read_text(encoding="utf-8")
        for fragment in (
            "Save to GitHub", "Load from GitHub",
            "GitHubPromptSettingsDialog", "def _on_import_prompt(",
            "def _on_export_prompt(", "library_snapshot()",
            "merge_library(", "def _audio_ready_for_library_transfer(",
            "def _library_changed(", "_GITHUB_SYNC_WORKERS",
        ):
            self.assertIn(fragment, source)
        self.assertIn("audio.refresh_after_library_import()", source)
        self.assertIn("def refresh_after_library_import(self):", audio)
        self.assertIn("Save or discard the current prompt draft", source)


if __name__ == "__main__":
    unittest.main()
