#!/usr/bin/env python3
"""Call one bounded trac-mcp tool from a JSON request.

This is intended for local recovery/automation paths that can reach the same
restricted broker socket as the MCP adapter. It deliberately reuses the
adapter's published tool schemas and broker transport rather than opening Trac
environments directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .server import TOOLS, broker

MAX_REQUEST_BYTES = 1024 * 1024


class RequestError(ValueError):
    """A request failed local schema validation."""


TOOLS_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_value(value: Any, schema: dict[str, Any], path: str) -> None:
    expected = schema.get("type")

    if expected == "object":
        if not isinstance(value, dict):
            raise RequestError(f"{path} must be an object")
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        missing = required - set(value)
        if missing:
            raise RequestError(
                f"{path} is missing required field(s): {', '.join(sorted(missing))}"
            )
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise RequestError(
                    f"{path} has unsupported field(s): {', '.join(sorted(extra))}"
                )
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                validate_value(item, child_schema, f"{path}.{key}")
        return

    if expected == "string":
        if not isinstance(value, str):
            raise RequestError(f"{path} must be a string")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise RequestError(f"{path} is shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise RequestError(f"{path} exceeds maxLength")
    elif expected == "integer":
        if not _is_integer(value):
            raise RequestError(f"{path} must be an integer")
        if "minimum" in schema and value < schema["minimum"]:
            raise RequestError(f"{path} is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise RequestError(f"{path} exceeds maximum")
    elif expected == "boolean":
        if not isinstance(value, bool):
            raise RequestError(f"{path} must be a boolean")
    elif expected == "array":
        if not isinstance(value, list):
            raise RequestError(f"{path} must be an array")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_value(item, item_schema, f"{path}[{index}]")
    elif expected is not None:
        raise RequestError(f"{path} uses unsupported schema type {expected!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise RequestError(f"{path} is not an allowed value")


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
        raise RequestError("tool must name one of the published trac-mcp tools")

    arguments = request.get("arguments", {})
    schema = TOOLS_BY_NAME[tool_name]["inputSchema"]
    validate_value(arguments, schema, "arguments")
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


def call_request(request: Any) -> Any:
    tool_name, arguments = validate_request(request)
    operation = tool_name[5:] if tool_name.startswith("trac_") else tool_name
    payload = {"op": operation}
    payload.update(arguments)
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
        help="list published trac-mcp tool names and exit",
    )
    args = parser.parse_args(argv)

    if args.list_tools:
        for name in sorted(TOOLS_BY_NAME):
            print(name)
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

    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
