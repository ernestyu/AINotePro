"""Safe structured Provider failures must never expose service error bodies."""
import io
import time
import unittest
from contextlib import redirect_stdout

from ainotepro.services.text._diagnostics import ProviderRequestError, request_failed


class Response:
    def __init__(self, status, error):
        self.status_code = status
        self.error = error

    def json(self):
        return {"error": self.error}


class ProviderErrorsTests(unittest.TestCase):
    def failure(self, status, code=None, message="secret=THIS_MUST_NOT_LEAK"):
        response = Response(status, {"code": code, "message": message})
        output = io.StringIO()
        with redirect_stdout(output):
            failure = request_failed(
                "test", "m", "https://alice:password@server/v1/chat/completions?key=XXX",
                time.perf_counter(), RuntimeError(message), False, response)
        self.assertIsInstance(failure, ProviderRequestError)
        self.assertNotIn("THIS_MUST_NOT_LEAK", str(failure))
        self.assertNotIn("THIS_MUST_NOT_LEAK", output.getvalue())
        self.assertNotIn("password", output.getvalue())
        self.assertNotIn("XXX", output.getvalue())
        return failure

    def test_context_error_requires_structured_code(self):
        self.assertEqual(self.failure(400, "context_length_exceeded").category,
                         "context-or-output-limit")
        self.assertEqual(self.failure(400, "anything_else").category, "unknown")
        self.assertEqual(self.failure(400, None).category, "unknown")

    def test_status_categories(self):
        for status, expected in (
            (401, "auth"), (403, "auth"), (404, "invalid-model-or-endpoint"),
            (429, "retryable"), (500, "retryable"), (503, "retryable"),
        ):
            with self.subTest(status=status):
                self.assertEqual(self.failure(status).category, expected)

    def test_malicious_code_never_enters_summary(self):
        exc = self.failure(400, "evil\nAUTHORITY=secret")
        self.assertNotIn("evil", exc.safe_summary)
        self.assertEqual(exc.service_code, "")

    def test_model_code_is_specific(self):
        self.assertEqual(self.failure(400, "model_not_found").category,
                         "invalid-model-or-endpoint")


if __name__ == "__main__":
    unittest.main()
