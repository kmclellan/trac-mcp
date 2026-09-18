#!/usr/bin/env python3
"""Call one bounded trac-mcp tool from a JSON request.

This is intended for trusted local recovery/automation paths that can reach the
same restricted broker socket as the MCP adapter. It reuses every published MCP
tool schema and adds an explicit local-only registry for guarded administrative,
destructive, batch and wiki-file operations. Trac environments are still
reached only through the constrained broker.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from .server import (
    E,
    TOOLS,
    SchemaValidationError,
    broker,
    tool,
    validate_value as validate_schema_value,
)

MAX_REQUEST_BYTES = 1024 * 1024
MAX_WIKI_FILE_BYTES = 50000


class RequestError(ValueError):
    """A request failed local schema validation."""


DELETE_CONFIRM = {"type": "string", "enum": ["DELETE"]}
IDEMPOTENCY = {"type": "string", "minLength": 8, "maxLength": 128}
PROJECT_KINDS = {"type": "string", "enum": ["component", "milestone", "version"]}
ENUM_KINDS = {
    "type": "string",
    "enum": ["priority", "resolution", "severity", "status", "type"],
}
MUTABLE_ENUM_KINDS = {
    "type": "string",
    "enum": ["priority", "resolution", "severity", "type"],
}

TICKET_CREATE_ITEM = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "maxLength": 500},
        "description": {"type": "string", "maxLength": 50000},
        "fields": {"type": "object"},
        "action": {"type": "string", "maxLength": 100},
        "action_fields": {"type": "object"},
    },
    "required": ["summary"],
    "additionalProperties": False,
}
TICKET_UPDATE_ITEM = {
    "type": "object",
    "properties": {
        "ticket_id": {"type": "integer", "minimum": 1},
        "expected_changed": {"type": "integer", "minimum": 0},
        "fields": {"type": "object"},
        "comment": {"type": "string", "maxLength": 5000},
        "action": {"type": "string", "maxLength": 100},
        "action_fields": {"type": "object"},
    },
    "required": ["ticket_id", "expected_changed"],
    "additionalProperties": False,
}
TICKET_DELETE_ITEM = {
    "type": "object",
    "properties": {
        "ticket_id": {"type": "integer", "minimum": 1},
        "expected_changed": {"type": "integer", "minimum": 0},
    },
    "required": ["ticket_id", "expected_changed"],
    "additionalProperties": False,
}

LOCAL_ONLY_TOOLS = [
    tool(
        "trac_ticket_delete",
        "Permanently delete one ticket after revision and explicit confirmation checks. Local CLI only.",
        dict(E, ticket_id={"type": "integer", "minimum": 1},
             expected_changed={"type": "integer", "minimum": 0},
             confirm=DELETE_CONFIRM, idempotency_key=IDEMPOTENCY),
        ["environment", "ticket_id", "expected_changed", "confirm", "idempotency_key"],
    ),
    tool(
        "trac_ticket_batch_create",
        "Create up to 50 tickets with per-item idempotency. Local CLI only.",
        dict(E, items={"type": "array", "minItems": 1, "maxItems": 50,
                      "items": TICKET_CREATE_ITEM},
             idempotency_key=IDEMPOTENCY),
        ["environment", "items", "idempotency_key"],
    ),
    tool(
        "trac_ticket_batch_update",
        "Revision-guarded update of up to 50 tickets. Local CLI only.",
        dict(E, items={"type": "array", "minItems": 1, "maxItems": 50,
                      "items": TICKET_UPDATE_ITEM},
             idempotency_key=IDEMPOTENCY),
        ["environment", "items", "idempotency_key"],
    ),
    tool(
        "trac_ticket_batch_delete",
        "Permanently delete up to 50 tickets after explicit confirmation. Local CLI only.",
        dict(E, items={"type": "array", "minItems": 1, "maxItems": 50,
                      "items": TICKET_DELETE_ITEM},
             confirm=DELETE_CONFIRM, idempotency_key=IDEMPOTENCY),
        ["environment", "items", "confirm", "idempotency_key"],
    ),
    tool(
        "trac_project_item_delete",
        "Delete a component, milestone or version after snapshot and confirmation checks. Local CLI only.",
        dict(E, kind=PROJECT_KINDS, name={"type": "string", "maxLength": 200},
             expected={"type": "object"}, confirm=DELETE_CONFIRM,
             idempotency_key=IDEMPOTENCY),
        ["environment", "kind", "name", "expected", "confirm", "idempotency_key"],
    ),
    tool(
        "trac_enum_create",
        "Create a priority, resolution, severity or type enum value. Local CLI only.",
        dict(E, kind=MUTABLE_ENUM_KINDS, name={"type": "string", "maxLength": 200},
             description={"type": "string", "maxLength": 1000},
             value={"type": "string", "maxLength": 50},
             idempotency_key=IDEMPOTENCY),
        ["environment", "kind", "name", "idempotency_key"],
    ),
    tool(
        "trac_enum_delete",
        "Delete a ticket enum value after snapshot and confirmation checks. Local CLI only.",
        dict(E, kind=MUTABLE_ENUM_KINDS, name={"type": "string", "maxLength": 200},
             expected={"type": "object"}, confirm=DELETE_CONFIRM,
             idempotency_key=IDEMPOTENCY),
        ["environment", "kind", "name", "expected", "confirm", "idempotency_key"],
    ),
    tool(
        "trac_attachment_delete",
        "Delete a ticket or wiki attachment after target-revision and confirmation checks. Local CLI only.",
        dict(E, realm={"type": "string", "enum": ["ticket", "wiki"]},
             resource={"type": "string", "maxLength": 200},
             filename={"type": "string", "maxLength": 255},
             expected_revision={"type": "integer", "minimum": 0},
             confirm=DELETE_CONFIRM, idempotency_key=IDEMPOTENCY),
        ["environment", "realm", "resource", "filename", "expected_revision",
         "confirm", "idempotency_key"],
    ),
    tool(
        "trac_wiki_delete",
        "Permanently delete a wiki page after revision and explicit confirmation checks. Local CLI only.",
        dict(E, page={"type": "string", "maxLength": 200},
             expected_version={"type": "integer", "minimum": 1},
             confirm=DELETE_CONFIRM, idempotency_key=IDEMPOTENCY),
        ["environment", "page", "expected_version", "confirm", "idempotency_key"],
    ),
    tool(
        "trac_wiki_file_detect_format",
        "Detect whether a local text file looks like Markdown or TracWiki. Local CLI only.",
        {
            "path": {"type": "string", "maxLength": 4096},
        },
        ["path"],
    ),
    tool(
        "trac_wiki_file_pull",
        "Pull a wiki page to a local file as stored TracWiki. Local CLI only.",
        dict(E, page={"type": "string", "maxLength": 200},
             output_path={"type": "string", "maxLength": 4096},
             overwrite={"type": "boolean"}),
        ["environment", "page", "output_path"],
    ),
    tool(
        "trac_wiki_file_push",
        "Push a local TracWiki file to a revision-guarded wiki page. Markdown is detected and rejected rather than silently converted. Local CLI only.",
        dict(E, page={"type": "string", "maxLength": 200},
             input_path={"type": "string", "maxLength": 4096},
             expected_version={"type": "integer", "minimum": 0},
             format={"type": "string", "enum": ["auto", "tracwiki", "markdown"]},
             comment={"type": "string", "maxLength": 1000}),
        ["environment", "page", "input_path", "expected_version"],
    ),
]

MCP_TOOLS_BY_NAME = {item["name"]: item for item in TOOLS}
TOOLS_BY_NAME = {
    **MCP_TOOLS_BY_NAME,
    **{item["name"]: item for item in LOCAL_ONLY_TOOLS},
}


def validate_request(request: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(request, dict):
        raise RequestError("request must be a JSON object")

    allowed = {"tool", "arguments"}
    extra = set(request) - allowed
    if extra:
        raise RequestError(
            "request has unsupported field(s): " + ", ".join(sorted(extra))
        )

    tool_name = request.get("tool")
    if not isinstance(tool_name, str) or tool_name not in TOOLS_BY_NAME:
        raise RequestError("tool must name one of the available trac-mcp-call tools")

    arguments = request.get("arguments", {})
    schema = TOOLS_BY_NAME[tool_name]["inputSchema"]
    try:
        validate_schema_value(arguments, schema, "arguments")
    except SchemaValidationError as exc:
        raise RequestError(str(exc)) from exc
    return tool_name, arguments


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RequestError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_request(path: str) -> Any:
    if path == "-":
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    else:
        request_path = Path(path)
        if request_path.is_symlink():
            raise RequestError("request file must not be a symlink")
        with request_path.open("rb") as stream:
            raw = stream.read(MAX_REQUEST_BYTES + 1)

    if len(raw) > MAX_REQUEST_BYTES:
        raise RequestError("request exceeds maximum size")
    if not raw:
        raise RequestError("request is empty")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestError(f"invalid UTF-8 JSON request: {exc}") from exc



def _read_local_text(path_value: str) -> tuple[Path, str, int]:
    path = Path(path_value)
    if path.is_symlink():
        raise RequestError("local file must not be a symlink")
    if not path.is_file():
        raise RequestError("local file must be an existing regular file")
    size = path.stat().st_size
    if size > MAX_WIKI_FILE_BYTES:
        raise RequestError("local wiki file exceeds maximum size")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RequestError("local wiki file must be UTF-8 text") from exc
    return path, text, len(raw)


def _detect_text_format(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".wiki", ".trac", ".tracwiki", ".tw"}:
        return "tracwiki"

    in_markdown_fence = False
    in_trac_fence = False
    visible_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not in_trac_fence and stripped.startswith("```"):
            in_markdown_fence = not in_markdown_fence
            continue
        if not in_markdown_fence and stripped.startswith("{{{"):
            in_trac_fence = True
            continue
        if in_trac_fence and "}}}" in stripped:
            in_trac_fence = False
            continue
        if not in_markdown_fence and not in_trac_fence:
            visible_lines.append(line)

    visible = "\n".join(visible_lines)
    if re.search(r"^={1,6}\s+.+?\s+={1,6}\s*$", visible, re.MULTILINE):
        return "tracwiki"
    if re.search(r"^#{1,6}\s+\S", visible, re.MULTILINE):
        return "markdown"

    markdown_score = text.count("**") + text.count("```") + text.count("](")
    tracwiki_score = text.count("'''") + text.count("{{{") + text.count("[[")
    return "markdown" if markdown_score > tracwiki_score else "tracwiki"


def _write_local_text(path_value: str, text: str, overwrite: bool) -> tuple[Path, int]:
    path = Path(path_value)
    if path.is_symlink():
        raise RequestError("output file must not be a symlink")
    if path.exists():
        if not path.is_file():
            raise RequestError("output path must be a regular file")
        if not overwrite:
            raise RequestError("output file already exists; set overwrite=true")
    parent = path.parent if str(path.parent) else Path(".")
    if parent.is_symlink() or not parent.is_dir():
        raise RequestError("output parent must be an existing non-symlink directory")

    encoded = text.encode("utf-8")
    if len(encoded) > MAX_WIKI_FILE_BYTES:
        raise RequestError("wiki page exceeds local file maximum size")

    fd, temp_name = tempfile.mkstemp(prefix=".trac-mcp-", dir=str(parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return path, len(encoded)


def _call_local_file_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    if tool_name == "trac_wiki_file_detect_format":
        path, text, size = _read_local_text(arguments["path"])
        return {
            "path": str(path),
            "format": _detect_text_format(path, text),
            "size_bytes": size,
        }

    if tool_name == "trac_wiki_file_pull":
        result = broker(
            {
                "op": "wiki_get",
                "environment": arguments["environment"],
                "page": arguments["page"],
            }
        )
        path, size = _write_local_text(
            arguments["output_path"],
            result["text"],
            bool(arguments.get("overwrite", False)),
        )
        return {
            "environment": arguments["environment"],
            "page": result["page"],
            "version": result["version"],
            "output_path": str(path),
            "format": "tracwiki",
            "size_bytes": size,
        }

    if tool_name == "trac_wiki_file_push":
        path, text, size = _read_local_text(arguments["input_path"])
        requested = arguments.get("format", "auto")
        detected = _detect_text_format(path, text)
        source_format = detected if requested == "auto" else requested
        if source_format == "markdown":
            raise RequestError(
                "Markdown input is not auto-converted: convert it to TracWiki "
                "explicitly, or pass format=tracwiki only when the file is "
                "already valid TracWiki"
            )
        result = broker(
            {
                "op": "wiki_update",
                "environment": arguments["environment"],
                "page": arguments["page"],
                "expected_version": arguments["expected_version"],
                "text": text,
                "comment": arguments.get(
                    "comment", "Updated from local TracWiki file"
                ),
            }
        )
        return {
            "environment": arguments["environment"],
            "page": result["page"],
            "version": result["version"],
            "input_path": str(path),
            "format": "tracwiki",
            "detected_format": detected,
            "size_bytes": size,
        }

    raise RequestError("unsupported local file tool")


LOCAL_FILE_TOOL_NAMES = {
    "trac_wiki_file_detect_format",
    "trac_wiki_file_pull",
    "trac_wiki_file_push",
}

def call_request(request: Any) -> Any:
    tool_name, arguments = validate_request(request)
    if tool_name in LOCAL_FILE_TOOL_NAMES:
        return _call_local_file_tool(tool_name, arguments)
    operation = tool_name[5:] if tool_name.startswith("trac_") else tool_name
    payload = dict(arguments)
    payload["op"] = operation
    return broker(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Call one constrained trac-mcp tool from a JSON request."
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="-",
        help="JSON request file, or - for stdin (default)",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="list all local CLI tool names (MCP-visible plus local-only) and exit",
    )
    parser.add_argument(
        "--list-mcp-tools",
        action="store_true",
        help="list only tools advertised by the MCP server and exit",
    )
    parser.add_argument(
        "--list-local-tools",
        action="store_true",
        help="list only extra tools available to the local CLI and exit",
    )
    args = parser.parse_args(argv)

    if args.list_tools:
        for name in sorted(TOOLS_BY_NAME):
            print(name)
        return 0
    if args.list_mcp_tools:
        for name in sorted(MCP_TOOLS_BY_NAME):
            print(name)
        return 0
    if args.list_local_tools:
        for item in sorted(tool["name"] for tool in LOCAL_ONLY_TOOLS):
            print(item)
        return 0

    try:
        request = read_request(args.request)
        output = call_request(request)
    except RequestError as exc:
        print(f"trac-mcp-call: request rejected: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"trac-mcp-call: broker error: {exc}", file=sys.stderr)
        return 3

    print(json.dumps(output, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
