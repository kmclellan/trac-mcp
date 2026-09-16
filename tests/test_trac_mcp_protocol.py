#!/usr/bin/env python3
import json
import subprocess
import os
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
        self.assertEqual(len(replies[1]["result"]["tools"]), 19)
        self.assertIn("trac_environments", {t["name"] for t in replies[1]["result"]["tools"]})


if __name__ == "__main__":
    unittest.main()
