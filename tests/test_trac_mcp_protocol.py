#!/usr/bin/env python3
import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def exchange(messages):
    payload = "".join(json.dumps(m, separators=(",", ":")) + "\n" for m in messages)
    p = subprocess.run(
        ["python3", "-m", "trac_mcp.server"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
        cwd=str(ROOT),
        env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
    )
    return [json.loads(line) for line in p.stdout.splitlines() if line.strip()]


def exchange_with_fake_broker(message, broker_result):
    with tempfile.TemporaryDirectory() as tmp:
        socket_path = str(Path(tmp) / "trac.sock")
        ready = threading.Event()
        received = []
        errors = []

        def serve():
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                server.bind(socket_path)
                server.listen(1)
                ready.set()
                conn, _ = server.accept()
                try:
                    chunks = []
                    while True:
                        chunk = conn.recv(8192)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    received.append(json.loads(b"".join(chunks).decode("utf-8")))
                    response = {"ok": True, "result": broker_result}
                    conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
                finally:
                    conn.close()
            except Exception as exc:
                errors.append(exc)
                ready.set()
            finally:
                server.close()

        thread = threading.Thread(target=serve)
        thread.start()
        if not ready.wait(2):
            raise AssertionError("fake broker did not start")

        env = dict(
            os.environ,
            PYTHONPATH=str(ROOT / "src"),
            TRAC_MCP_SOCKET=socket_path,
            TRAC_MCP_ENVIRONMENTS="example",
        )
        payload = json.dumps(message, separators=(",", ":")) + "\n"
        p = subprocess.run(
            ["python3", "-m", "trac_mcp.server"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            cwd=str(ROOT),
            env=env,
        )
        thread.join(2)
        if thread.is_alive():
            raise AssertionError("fake broker did not finish")
        if errors:
            raise errors[0]
        replies = [
            json.loads(line) for line in p.stdout.splitlines() if line.strip()
        ]
        return replies, received


class TracMcpProtocolTests(unittest.TestCase):
    def test_echoes_supported_modern_protocol(self):
        replies = exchange([
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
        ])
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(replies[0]["result"]["serverInfo"]["version"], "0.4.0")
        instructions = replies[0]["result"]["instructions"]
        self.assertIn("preferred application-level interface", instructions)
        self.assertIn("Do not use direct database writes", instructions)

    def test_falls_back_for_unknown_protocol(self):
        replies = exchange([
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "future-unknown"},
            }
        ])
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2024-11-05")

    def test_tools_list_unchanged_after_modern_handshake(self):
        replies = exchange([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ])
        self.assertEqual(len(replies), 2)
        tool_items = replies[1]["result"]["tools"]
        tools = {t["name"] for t in tool_items}
        self.assertEqual(len(tools), 26)
        self.assertTrue(all("outputSchema" in t for t in tool_items))
        self.assertTrue(
            all(t["outputSchema"].get("type") == "object" for t in tool_items)
        )

        def assert_strict_schema(schema, path="$"):
            self.assertNotEqual(schema, {}, path)
            if schema.get("type") == "object":
                properties = schema.get("properties")
                self.assertIsInstance(properties, dict, path)
                self.assertFalse(schema.get("additionalProperties"), path)
                self.assertEqual(
                    set(schema.get("required", [])),
                    set(properties),
                    path,
                )
            for key, value in schema.items():
                if isinstance(value, dict):
                    assert_strict_schema(value, path + "." + key)
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        if isinstance(item, dict):
                            assert_strict_schema(
                                item, "%s.%s[%d]" % (path, key, index)
                            )

        for item in tool_items:
            assert_strict_schema(
                item["outputSchema"], item["name"] + ".outputSchema"
            )

        self.assertIn("trac_environments", tools)
        self.assertIn("trac_ticket_actions", tools)
        self.assertIn("trac_wiki_recent_changes", tools)
        self.assertIn("trac_project_item_list", tools)
        self.assertIn("trac_enum_list", tools)
        self.assertNotIn("trac_ticket_delete", tools)
        self.assertNotIn("trac_wiki_delete", tools)

    def test_unadvertised_local_tool_cannot_be_called_through_mcp(self):
        replies = exchange([
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "trac_ticket_delete",
                    "arguments": {
                        "environment": "example",
                        "ticket_id": 1,
                        "expected_changed": 0,
                        "confirm": "DELETE",
                        "idempotency_key": "delete-12345678",
                    },
                },
            }
        ])
        self.assertEqual(len(replies), 1)
        result = replies[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("not advertised", result["content"][0]["text"])

    def test_unknown_tool_cannot_be_forwarded_to_broker(self):
        replies = exchange([
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {"name": "trac_shell", "arguments": {}},
            }
        ])
        self.assertEqual(len(replies), 1)
        result = replies[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("not advertised", result["content"][0]["text"])

    def test_valid_advertised_tool_reaches_broker_with_fixed_operation(self):
        replies, received = exchange_with_fake_broker(
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {
                    "name": "trac_ping",
                    "arguments": {"environment": "example"},
                },
            },
            {
                "environment": "example",
                "project_name": "Fixture",
                "trac_version": "test",
            },
        )
        self.assertEqual(
            received,
            [{"environment": "example", "op": "ping"}],
        )
        result = replies[0]["result"]
        self.assertFalse(result["isError"])
        text_value = json.loads(result["content"][0]["text"])
        self.assertEqual(text_value["trac_version"], "test")
        self.assertEqual(result["structuredContent"], text_value)

    def test_invalid_broker_output_is_rejected_against_output_schema(self):
        replies, received = exchange_with_fake_broker(
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "tools/call",
                "params": {
                    "name": "trac_project_item_get",
                    "arguments": {
                        "environment": "example",
                        "kind": "component",
                        "name": "Fixture",
                    },
                },
            },
            {
                "kind": "not-a-project-kind",
                "name": "Fixture",
                "description": "",
            },
        )
        self.assertEqual(received[0]["op"], "project_item_get")
        result = replies[0]["result"]
        self.assertTrue(result["isError"])
        self.assertNotIn("structuredContent", result)
        self.assertIn("not an allowed value", result["content"][0]["text"])

    def test_nullable_date_is_forwarded_unchanged(self):
        replies, received = exchange_with_fake_broker(
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {
                    "name": "trac_project_item_update",
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
                },
            },
            {
                "kind": "milestone",
                "name": "M1",
                "description": "",
                "due": None,
                "completed": None,
            },
        )
        self.assertEqual(received[0]["op"], "project_item_update")
        self.assertIsNone(received[0]["due"])
        result = replies[0]["result"]
        self.assertFalse(result["isError"])
        raw = json.loads(result["content"][0]["text"])
        self.assertNotIn("owner", raw)
        self.assertNotIn("time", raw)
        self.assertEqual(
            result["structuredContent"],
            {
                "kind": "milestone",
                "name": "M1",
                "description": "",
                "owner": None,
                "due": None,
                "completed": None,
                "time": None,
            },
        )

    def test_dynamic_action_changes_are_normalized_for_structured_content(self):
        broker_result = {
            "ticket": {
                "id": 1,
                "changed": 123,
                "summary": "T",
                "description": "",
                "status": "accepted",
                "type": "defect",
                "priority": "major",
                "milestone": "",
                "component": "",
                "owner": "MCP",
                "reporter": "MCP",
                "keywords": "",
                "resolution": "",
            },
            "duplicate": False,
            "action": "accept",
            "action_changes": {"status": "accepted", "owner": "MCP"},
        }
        replies, _ = exchange_with_fake_broker(
            {
                "jsonrpc": "2.0",
                "id": 15,
                "method": "tools/call",
                "params": {
                    "name": "trac_ticket_update",
                    "arguments": {
                        "environment": "example",
                        "ticket_id": 1,
                        "expected_changed": 122,
                    },
                },
            },
            broker_result,
        )
        result = replies[0]["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(json.loads(result["content"][0]["text"]), broker_result)
        self.assertEqual(
            result["structuredContent"]["action_changes"],
            [
                {"field": "owner", "value_json": '"MCP"'},
                {"field": "status", "value_json": '"accepted"'},
            ],
        )

    def test_operation_override_argument_is_rejected_before_broker(self):
        replies = exchange([
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "trac_ping",
                    "arguments": {
                        "environment": "example",
                        "op": "ticket_delete",
                        "ticket_id": 1,
                        "confirm": "DELETE",
                    },
                },
            }
        ])
        self.assertEqual(len(replies), 1)
        result = replies[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("unsupported field", result["content"][0]["text"])

    def test_invalid_environment_is_rejected_before_broker(self):
        replies = exchange([
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "trac_ping",
                    "arguments": {"environment": "not-allowed"},
                },
            }
        ])
        self.assertEqual(len(replies), 1)
        result = replies[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("not an allowed value", result["content"][0]["text"])

    def test_missing_required_argument_is_rejected_before_broker(self):
        replies = exchange([
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "trac_ticket_get", "arguments": {}},
            }
        ])
        self.assertEqual(len(replies), 1)
        result = replies[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("missing required field", result["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
