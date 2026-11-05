"""Offline GitHub library synchronization tests using a mocked HTTPS response."""
import base64
import io
import json
import os
import tempfile
import unittest
from urllib.error import HTTPError
from pathlib import Path
from unittest.mock import patch

from ainotepro.config.audio_profiles import default_profile
from ainotepro.core.prompt_bundle import make_bundle
from ainotepro.services import github_prompts as gh


class FakeResponse:
    def __init__(self, body):
        self.body = body
        self.status = 200
        self.headers = {"X-GitHub-Request-Id": "test-request-id"}

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
        self.assertEqual(len(requests), 3)  # repository, branch, contents
        self.assertEqual(requests[0].get_method(), "GET")
        self.assertIn("/branches/main", requests[1].full_url)
        self.assertEqual(requests[0].get_header("Authorization"),
                         "Bearer secret-token")
        self.assertNotIn("secret-token", requests[0].full_url)

    def test_nested_directory_path_uses_contents_api(self):
        library = bundle(3)
        calls = []

        def open_(req, timeout):
            calls.append(req.full_url)
            return FakeResponse(remote_document(library))

        settings = dict(self.settings, path="anki/ainotepro-library.json")
        with patch.object(gh._OPENER, "open", side_effect=open_):
            self.assertEqual(gh.load_from_github(settings, ""), library)
        self.assertIn("/contents/anki/ainotepro-library.json?ref=main", calls[2])

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
            if req.get_method() == "GET" and "/contents/" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
            if req.get_method() == "GET":
                return FakeResponse({"ok": True})
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

    def test_diagnostics_write_file_and_stdout_without_stderr_popup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "logs", "github_sync.log")
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(gh, "diagnostic_log_path", return_value=path), \
                 patch.object(gh.sys, "stdout", stdout), \
                 patch.object(gh.sys, "stderr", stderr):
                error = gh._log(gh.logging.ERROR, "check_repository", self.settings,
                                404, "request-123", "http_error", has_token=True)
            self.assertIsNone(error)
            self.assertTrue(os.path.isfile(path))
            with open(path, "r", encoding="utf-8") as inp:
                log = inp.read()
            self.assertIn("stage=check_repository status=404", log)
            self.assertIn("request_id=request-123", log)
            self.assertIn("token_present=True", log)
            self.assertNotIn("secret-token", log)
            self.assertIn("stage=check_repository status=404", stdout.getvalue())
            # Anki treats stderr as an error report, even without a traceback.
            self.assertEqual(stderr.getvalue(), "")

    def test_logging_failure_is_visible_without_stderr_popup(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        def blocked(*args, **kwargs):
            raise PermissionError("read-only log folder")
        def open_(req, timeout):
            raise HTTPError(req.full_url, 404, "Not Found",
                            {"X-GitHub-Request-Id": "blocked-log"}, None)
        with patch.object(gh._OPENER, "open", side_effect=open_), \
             patch.object(gh.os, "makedirs", side_effect=blocked), \
             patch.object(gh.sys, "stdout", stdout), \
             patch.object(gh.sys, "stderr", stderr):
            with self.assertRaises(gh.GitHubAPIError) as error:
                gh.fetch_remote(self.settings, "secret-token")
        message = str(error.exception)
        self.assertIn("Diagnostic logging failed", message)
        self.assertIn("PermissionError", message)
        self.assertIn("Diagnostic file write FAILED", stdout.getvalue())
        self.assertNotIn("secret-token", stdout.getvalue())
        self.assertNotIn("secret-token", message)
        self.assertEqual(stderr.getvalue(), "")

    def test_private_repo_404_is_not_treated_as_new_library(self):
        writes = []
        def open_(req, timeout):
            writes.append(req.get_method())
            raise HTTPError(req.full_url, 404, "Not Found",
                            {"X-GitHub-Request-Id": "private-repo-id"}, None)
        with patch.object(gh._OPENER, "open", side_effect=open_), \
             patch.object(gh, "_log"):
            with self.assertRaisesRegex(gh.GitHubAPIError, "check_repository.*HTTP 404"):
                gh.save_to_github(self.settings, "secret-token", bundle(2))
        self.assertEqual(writes, ["GET"])  # never PUT a private repo 404

    def test_missing_branch_does_not_try_create_file(self):
        methods = []
        def open_(req, timeout):
            methods.append(req.get_method())
            if "/branches/" in req.full_url:
                raise HTTPError(req.full_url, 404, "Not Found",
                                {"X-GitHub-Request-Id": "missing-branch"}, None)
            return FakeResponse({"ok": True})
        with patch.object(gh._OPENER, "open", side_effect=open_), \
             patch.object(gh, "_log"):
            with self.assertRaisesRegex(gh.GitHubAPIError, "check_branch.*HTTP 404"):
                gh.save_to_github(self.settings, "secret-token", bundle(2))
        self.assertEqual(methods, ["GET", "GET"])

    def test_permission_denied_reports_write_stage_and_request_id(self):
        def open_(req, timeout):
            if req.get_method() == "PUT":
                raise HTTPError(req.full_url, 403, "Forbidden",
                                {"X-GitHub-Request-Id": "write-rejected"}, None)
            if "/contents/" in req.full_url:
                raise HTTPError(req.full_url, 404, "Not Found", {}, None)
            return FakeResponse({"ok": True})
        with patch.object(gh._OPENER, "open", side_effect=open_), \
             patch.object(gh, "_log"):
            with self.assertRaises(gh.GitHubAPIError) as error:
                gh.save_to_github(self.settings, "secret-token", bundle(2))
        self.assertIn("stage=create_or_update_file", str(error.exception))
        self.assertIn("HTTP 403", str(error.exception))
        self.assertIn("write-rejected", str(error.exception))
        self.assertNotIn("secret-token", str(error.exception))

    def test_missing_contents_is_allowed_only_after_repository_preflight(self):
        calls = []
        def open_(req, timeout):
            calls.append(req.full_url)
            if "/contents/" in req.full_url:
                raise HTTPError(req.full_url, 404, "Not Found", {}, None)
            return FakeResponse({"ok": True})
        with patch.object(gh._OPENER, "open", side_effect=open_), \
             patch.object(gh, "_log"):
            self.assertEqual(gh.fetch_remote(self.settings, "secret-token"), (None, None))
        self.assertEqual(len(calls), 3)

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
