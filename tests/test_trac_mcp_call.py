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
        with self.assertRaisesRegex(call.RequestError, "available trac-mcp-call tools"):
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

    def test_local_admin_tools_are_available_to_cli_but_not_mcp(self):
        self.assertIn("trac_ticket_delete", call.TOOLS_BY_NAME)
        self.assertIn("trac_wiki_delete", call.TOOLS_BY_NAME)
        self.assertNotIn("trac_ticket_delete", call.MCP_TOOLS_BY_NAME)
        self.assertNotIn("trac_wiki_delete", call.MCP_TOOLS_BY_NAME)

    def test_delete_requires_explicit_confirmation(self):
        request = {
            "tool": "trac_ticket_delete",
            "arguments": {
                "environment": "example",
                "ticket_id": 7,
                "expected_changed": 123,
                "confirm": "yes",
                "idempotency_key": "delete-12345678",
            },
        }
        with self.assertRaisesRegex(call.RequestError, "allowed value"):
            call.validate_request(request)

    def test_batch_size_is_bounded(self):
        request = {
            "tool": "trac_ticket_batch_create",
            "arguments": {
                "environment": "example",
                "items": [{"summary": f"ticket {i}"} for i in range(51)],
                "idempotency_key": "batch-12345678",
            },
        }
        with self.assertRaisesRegex(call.RequestError, "too many items"):
            call.validate_request(request)


    def test_wiki_file_format_detection_is_local_only(self):
        self.assertIn("trac_wiki_file_detect_format", call.TOOLS_BY_NAME)
        self.assertNotIn(
            "trac_wiki_file_detect_format", call.MCP_TOOLS_BY_NAME
        )
        with tempfile.TemporaryDirectory() as tmp:
            markdown = Path(tmp) / "notes.md"
            markdown.write_text("# Heading\n\nText\n", encoding="utf-8")
            tracwiki = Path(tmp) / "notes.txt"
            tracwiki.write_text("= Heading =\n\n'''Bold'''\n", encoding="utf-8")

            md_result = call.call_request(
                {
                    "tool": "trac_wiki_file_detect_format",
                    "arguments": {"path": str(markdown)},
                }
            )
            tw_result = call.call_request(
                {
                    "tool": "trac_wiki_file_detect_format",
                    "arguments": {"path": str(tracwiki)},
                }
            )

        self.assertEqual(md_result["format"], "markdown")
        self.assertEqual(tw_result["format"], "tracwiki")

    def test_wiki_file_pull_writes_raw_tracwiki_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "WikiStart.tw"
            with patch.object(
                call,
                "broker",
                return_value={
                    "page": "WikiStart",
                    "version": 3,
                    "text": "= WikiStart =\n",
                    "author": "MCP",
                    "comment": "",
                },
            ) as broker:
                result = call.call_request(
                    {
                        "tool": "trac_wiki_file_pull",
                        "arguments": {
                            "environment": "example",
                            "page": "WikiStart",
                            "output_path": str(output),
                        },
                    }
                )

            self.assertEqual(output.read_text(encoding="utf-8"), "= WikiStart =\n")
            self.assertEqual(result["format"], "tracwiki")
            broker.assert_called_once_with(
                {"op": "wiki_get", "environment": "example", "page": "WikiStart"}
            )

    def test_wiki_file_push_rejects_detected_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "notes.md"
            source.write_text("# Heading\n", encoding="utf-8")
            with patch.object(call, "broker") as broker:
                with self.assertRaisesRegex(
                    call.RequestError, "not auto-converted"
                ):
                    call.call_request(
                        {
                            "tool": "trac_wiki_file_push",
                            "arguments": {
                                "environment": "example",
                                "page": "Notes",
                                "input_path": str(source),
                                "expected_version": 0,
                            },
                        }
                    )
            broker.assert_not_called()

    def test_wiki_file_push_sends_tracwiki_through_guarded_broker_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "notes.tw"
            source.write_text("= Heading =\n", encoding="utf-8")
            with patch.object(
                call,
                "broker",
                return_value={
                    "page": "Notes",
                    "version": 1,
                    "text": "= Heading =\n",
                    "author": "MCP",
                    "comment": "file push",
                },
            ) as broker:
                result = call.call_request(
                    {
                        "tool": "trac_wiki_file_push",
                        "arguments": {
                            "environment": "example",
                            "page": "Notes",
                            "input_path": str(source),
                            "expected_version": 0,
                            "comment": "file push",
                        },
                    }
                )

            self.assertEqual(result["version"], 1)
            broker.assert_called_once_with(
                {
                    "op": "wiki_update",
                    "environment": "example",
                    "page": "Notes",
                    "expected_version": 0,
                    "text": "= Heading =\n",
                    "comment": "file push",
                }
            )

    def test_wiki_file_pull_refuses_output_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.tw"
            target.write_text("old", encoding="utf-8")
            link = Path(tmp) / "link.tw"
            link.symlink_to(target)
            with patch.object(
                call,
                "broker",
                return_value={
                    "page": "WikiStart",
                    "version": 1,
                    "text": "new",
                    "author": "MCP",
                    "comment": "",
                },
            ):
                with self.assertRaisesRegex(call.RequestError, "symlink"):
                    call.call_request(
                        {
                            "tool": "trac_wiki_file_pull",
                            "arguments": {
                                "environment": "example",
                                "page": "WikiStart",
                                "output_path": str(link),
                                "overwrite": True,
                            },
                        }
                    )
            self.assertEqual(target.read_text(encoding="utf-8"), "old")

    def test_nullable_project_dates_use_shared_schema(self):
        request = {
            "tool": "trac_project_item_update",
            "arguments": {
                "environment": "example",
                "kind": "milestone",
                "name": "M1",
                "expected": {
                    "kind": "milestone",
                    "name": "M1",
                    "description": "",
                    "due": 123,
                    "completed": None,
                },
                "due": None,
            },
        }
        tool_name, arguments = call.validate_request(request)
        self.assertEqual(tool_name, "trac_project_item_update")
        self.assertIsNone(arguments["due"])

        request["arguments"]["due"] = "not-a-time"
        with self.assertRaisesRegex(call.RequestError, "must be an integer"):
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
