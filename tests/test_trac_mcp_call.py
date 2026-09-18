#!/usr/bin/env python3
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from trac_mcp import call


class TracMcpCallTests(unittest.TestCase):
    def valid_comment_request(self):
        return {
            "tool": "trac_ticket_comment",
            "arguments": {
                "environment": "example",
                "ticket_id": 7,
                "expected_changed": 123456,
                "comment": "Comment with Markdown `code`.",
                "idempotency_key": "comment-12345678",
            },
        }

    def test_valid_request_reuses_published_tool_schema_and_broker(self):
        request = self.valid_comment_request()
        with patch.object(call, "broker", return_value={"ticket": {"id": 7}}) as broker:
            result = call.call_request(request)

        self.assertEqual(result, {"ticket": {"id": 7}})
        broker.assert_called_once_with(
            {
                "op": "ticket_comment",
                "environment": "example",
                "ticket_id": 7,
                "expected_changed": 123456,
                "comment": "Comment with Markdown `code`.",
                "idempotency_key": "comment-12345678",
            }
        )

    def test_unknown_tool_is_rejected(self):
        request = {"tool": "trac_shell", "arguments": {}}
        with self.assertRaisesRegex(call.RequestError, "published trac-mcp tools"):
            call.validate_request(request)

    def test_extra_tool_argument_is_rejected(self):
        request = self.valid_comment_request()
        request["arguments"]["shell"] = "id"
        with self.assertRaisesRegex(call.RequestError, "unsupported field"):
            call.validate_request(request)

    def test_missing_revision_guard_is_rejected(self):
        request = self.valid_comment_request()
        del request["arguments"]["expected_changed"]
        with self.assertRaisesRegex(call.RequestError, "missing required"):
            call.validate_request(request)

    def test_boolean_is_not_accepted_as_integer(self):
        request = self.valid_comment_request()
        request["arguments"]["ticket_id"] = True
        with self.assertRaisesRegex(call.RequestError, "must be an integer"):
            call.validate_request(request)

    def test_environment_must_come_from_adapter_allowlist(self):
        request = self.valid_comment_request()
        request["arguments"]["environment"] = "not-allowed"
        with self.assertRaisesRegex(call.RequestError, "allowed value"):
            call.validate_request(request)

    def test_symlink_request_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "request.json"
            target.write_text(json.dumps(self.valid_comment_request()), encoding="utf-8")
            link = Path(tmp) / "link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(call.RequestError, "symlink"):
                call.read_request(str(link))

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            path.write_text(
                '{"tool":"trac_environments","tool":"trac_ticket_get","arguments":{}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(call.RequestError, "duplicate JSON key"):
                call.read_request(str(path))

    def test_request_size_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.json"
            path.write_bytes(b"x" * (call.MAX_REQUEST_BYTES + 1))
            with self.assertRaisesRegex(call.RequestError, "maximum size"):
                call.read_request(str(path))

    def test_cli_prints_broker_result(self):
        request = self.valid_comment_request()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.object(call, "broker", return_value={"ok": "value"}):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    status = call.main([str(path)])

        self.assertEqual(status, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(json.loads(stdout.getvalue()), {"ok": "value"})

    def test_cli_returns_distinct_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text('{"tool":"trac_shell","arguments":{}}', encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = call.main([str(path)])

        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("request rejected", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
