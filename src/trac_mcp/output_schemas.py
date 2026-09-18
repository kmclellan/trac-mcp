"""Strict MCP output schemas and structured-result normalization.

The ChatGPT action scanner applies a stricter structured-output subset than
general JSON Schema. Every object therefore has a fixed property set,
additionalProperties=false, and every property is required. Raw broker JSON is
still returned as TextContent; only structuredContent is normalized.
"""

from __future__ import annotations

import json
from typing import Any


def obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


STRING = {"type": "string"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}
NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_INTEGER = {"type": ["integer", "null"]}

TICKET = obj(
    {
        "id": INTEGER,
        "changed": INTEGER,
        "summary": NULLABLE_STRING,
        "description": NULLABLE_STRING,
        "status": NULLABLE_STRING,
        "type": NULLABLE_STRING,
        "priority": NULLABLE_STRING,
        "milestone": NULLABLE_STRING,
        "component": NULLABLE_STRING,
        "owner": NULLABLE_STRING,
        "reporter": NULLABLE_STRING,
        "keywords": NULLABLE_STRING,
        "resolution": NULLABLE_STRING,
    }
)

PROJECT_ITEM = obj(
    {
        "kind": {"type": "string", "enum": ["component", "milestone", "version"]},
        "name": STRING,
        "description": NULLABLE_STRING,
        "owner": NULLABLE_STRING,
        "due": NULLABLE_INTEGER,
        "completed": NULLABLE_INTEGER,
        "time": NULLABLE_INTEGER,
    }
)

PROJECT_ITEM_CREATED = obj(
    dict(PROJECT_ITEM["properties"], duplicate=BOOLEAN)
)

ENUM_ITEM = obj(
    {
        "kind": {
            "type": "string",
            "enum": ["priority", "resolution", "severity", "status", "type"],
        },
        "name": STRING,
        "value": NULLABLE_STRING,
        "description": NULLABLE_STRING,
    }
)

WORKFLOW_ACTION = obj(
    {
        "name": STRING,
        "label": STRING,
        "hint": STRING,
        "input_fields": {"type": "array", "items": STRING},
    }
)

TICKET_FIELD = obj(
    {
        "name": STRING,
        "type": STRING,
        "label": STRING,
        "custom": BOOLEAN,
        "optional": BOOLEAN,
        "options": {"type": "array", "items": STRING},
        "value": NULLABLE_STRING,
        "format": NULLABLE_STRING,
        "max_size": NULLABLE_INTEGER,
    }
)

ATTACHMENT = obj(
    {
        "realm": {"type": "string", "enum": ["ticket", "wiki"]},
        "resource": STRING,
        "filename": STRING,
        "size": INTEGER,
        "author": NULLABLE_STRING,
        "description": NULLABLE_STRING,
    }
)

WIKI_PAGE = obj(
    {
        "page": STRING,
        "version": INTEGER,
        "text": STRING,
        "author": NULLABLE_STRING,
        "comment": NULLABLE_STRING,
    }
)

ACTION_CHANGE = obj(
    {
        "field": STRING,
        "value_json": STRING,
    }
)

TICKET_MUTATION = obj(
    {
        "ticket": TICKET,
        "duplicate": BOOLEAN,
        "action": NULLABLE_STRING,
        "action_changes": {"type": "array", "items": ACTION_CHANGE},
    }
)

OUTPUT_SCHEMAS = {
    "trac_environments": obj(
        {"environments": {"type": "array", "items": STRING}}
    ),
    "trac_ping": obj(
        {
            "environment": STRING,
            "project_name": STRING,
            "trac_version": STRING,
        }
    ),
    "trac_server_time": obj(
        {"unix_timestamp": INTEGER, "iso_utc": STRING}
    ),
    "trac_ticket_get": TICKET,
    "trac_ticket_query": obj(
        {"tickets": {"type": "array", "items": TICKET}}
    ),
    "trac_ticket_timeline": obj(
        {
            "ticket_id": INTEGER,
            "timeline": {
                "type": "array",
                "items": obj(
                    {
                        "time": INTEGER,
                        "author": NULLABLE_STRING,
                        "field": NULLABLE_STRING,
                        "old": NULLABLE_STRING,
                        "new": NULLABLE_STRING,
                        "permanent": BOOLEAN,
                    }
                ),
            },
        }
    ),
    "trac_ticket_metadata": obj(
        {
            "types": {"type": "array", "items": STRING},
            "priorities": {"type": "array", "items": STRING},
            "components": {"type": "array", "items": STRING},
            "milestones": {"type": "array", "items": STRING},
            "versions": {"type": "array", "items": STRING},
            "resolutions": {"type": "array", "items": STRING},
            "owners": {"type": "array", "items": STRING},
        }
    ),
    "trac_ticket_fields": obj(
        {"fields": {"type": "array", "items": TICKET_FIELD}}
    ),
    "trac_ticket_actions": obj(
        {
            "ticket_id": INTEGER,
            "authname": STRING,
            "actions": {"type": "array", "items": WORKFLOW_ACTION},
        }
    ),
    "trac_project_item_list": obj(
        {
            "kind": {"type": "string", "enum": ["component", "milestone", "version"]},
            "items": {"type": "array", "items": PROJECT_ITEM},
            "total": INTEGER,
        }
    ),
    "trac_project_item_get": PROJECT_ITEM,
    "trac_enum_list": obj(
        {
            "kind": {
                "type": "string",
                "enum": ["priority", "resolution", "severity", "status", "type"],
            },
            "items": {"type": "array", "items": ENUM_ITEM},
        }
    ),
    "trac_project_item_create": PROJECT_ITEM_CREATED,
    "trac_project_item_update": PROJECT_ITEM,
    "trac_ticket_create": TICKET_MUTATION,
    "trac_ticket_update": TICKET_MUTATION,
    "trac_ticket_comment": obj(
        {"ticket": TICKET, "duplicate": BOOLEAN}
    ),
    "trac_wiki_recent_changes": obj(
        {
            "changes": {
                "type": "array",
                "items": obj(
                    {
                        "page": STRING,
                        "version": INTEGER,
                        "time": INTEGER,
                        "author": NULLABLE_STRING,
                        "comment": NULLABLE_STRING,
                    }
                ),
            },
            "limit": INTEGER,
        }
    ),
    "trac_wiki_list": obj(
        {"pages": {"type": "array", "items": STRING}}
    ),
    "trac_wiki_search": obj(
        {
            "results": {
                "type": "array",
                "items": obj(
                    {"page": STRING, "version": INTEGER, "excerpt": STRING}
                ),
            }
        }
    ),
    "trac_attachment_list": obj(
        {"attachments": {"type": "array", "items": ATTACHMENT}}
    ),
    "trac_attachment_upload": obj(
        {
            "realm": {"type": "string", "enum": ["ticket", "wiki"]},
            "resource": STRING,
            "filename": STRING,
            "size": NULLABLE_INTEGER,
            "duplicate": BOOLEAN,
        }
    ),
    "trac_attachment_get": obj(
        dict(ATTACHMENT["properties"], content_base64=STRING)
    ),
    "trac_wiki_get": WIKI_PAGE,
    "trac_wiki_history": obj(
        {
            "history": {
                "type": "array",
                "items": obj(
                    {
                        "version": INTEGER,
                        "time": INTEGER,
                        "author": NULLABLE_STRING,
                        "comment": NULLABLE_STRING,
                    }
                ),
            }
        }
    ),
    "trac_wiki_update": WIKI_PAGE,
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _string(value: Any) -> str:
    text = _text(value)
    return "" if text is None else text


def _strings(values: Any) -> list[str]:
    return [_string(value) for value in (values or [])]


def _integer_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _ticket(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(value["id"]),
        "changed": int(value["changed"]),
        "summary": _text(value.get("summary")),
        "description": _text(value.get("description")),
        "status": _text(value.get("status")),
        "type": _text(value.get("type")),
        "priority": _text(value.get("priority")),
        "milestone": _text(value.get("milestone")),
        "component": _text(value.get("component")),
        "owner": _text(value.get("owner")),
        "reporter": _text(value.get("reporter")),
        "keywords": _text(value.get("keywords")),
        "resolution": _text(value.get("resolution")),
    }


def _project_item(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": _string(value.get("kind")),
        "name": _string(value.get("name")),
        "description": _text(value.get("description")),
        "owner": _text(value.get("owner")),
        "due": _integer_or_none(value.get("due")),
        "completed": _integer_or_none(value.get("completed")),
        "time": _integer_or_none(value.get("time")),
    }


def _attachment(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "realm": _string(value.get("realm")),
        "resource": _string(value.get("resource")),
        "filename": _string(value.get("filename")),
        "size": int(value.get("size") or 0),
        "author": _text(value.get("author")),
        "description": _text(value.get("description")),
    }


def _wiki_page(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "page": _string(value.get("page")),
        "version": int(value.get("version") or 0),
        "text": _string(value.get("text")),
        "author": _text(value.get("author")),
        "comment": _text(value.get("comment")),
    }


def _action_changes(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return []
    return [
        {
            "field": str(field),
            "value_json": json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        }
        for field, item in sorted(value.items())
    ]


def normalize_output(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Return strict structuredContent while preserving raw TextContent elsewhere."""

    if name == "trac_environments":
        return {"environments": _strings(raw.get("environments"))}
    if name == "trac_ping":
        return {
            "environment": _string(raw.get("environment")),
            "project_name": _string(raw.get("project_name")),
            "trac_version": _string(raw.get("trac_version")),
        }
    if name == "trac_server_time":
        return {
            "unix_timestamp": int(raw.get("unix_timestamp") or 0),
            "iso_utc": _string(raw.get("iso_utc")),
        }
    if name == "trac_ticket_get":
        return _ticket(raw)
    if name == "trac_ticket_query":
        return {"tickets": [_ticket(item) for item in raw.get("tickets", [])]}
    if name == "trac_ticket_timeline":
        return {
            "ticket_id": int(raw.get("ticket_id") or 0),
            "timeline": [
                {
                    "time": int(item.get("time") or 0),
                    "author": _text(item.get("author")),
                    "field": _text(item.get("field")),
                    "old": _text(item.get("old")),
                    "new": _text(item.get("new")),
                    "permanent": bool(item.get("permanent")),
                }
                for item in raw.get("timeline", [])
            ],
        }
    if name == "trac_ticket_metadata":
        return {
            key: _strings(raw.get(key))
            for key in (
                "types",
                "priorities",
                "components",
                "milestones",
                "versions",
                "resolutions",
                "owners",
            )
        }
    if name == "trac_ticket_fields":
        return {
            "fields": [
                {
                    "name": _string(item.get("name")),
                    "type": _string(item.get("type")),
                    "label": _string(item.get("label")),
                    "custom": bool(item.get("custom", False)),
                    "optional": bool(item.get("optional", False)),
                    "options": _strings(item.get("options")),
                    "value": _text(item.get("value")),
                    "format": _text(item.get("format")),
                    "max_size": _integer_or_none(item.get("max_size")),
                }
                for item in raw.get("fields", [])
            ]
        }
    if name == "trac_ticket_actions":
        return {
            "ticket_id": int(raw.get("ticket_id") or 0),
            "authname": _string(raw.get("authname")),
            "actions": [
                {
                    "name": _string(item.get("name")),
                    "label": _string(item.get("label")),
                    "hint": _string(item.get("hint")),
                    "input_fields": _strings(item.get("input_fields")),
                }
                for item in raw.get("actions", [])
            ],
        }
    if name == "trac_project_item_list":
        return {
            "kind": _string(raw.get("kind")),
            "items": [_project_item(item) for item in raw.get("items", [])],
            "total": int(raw.get("total") or 0),
        }
    if name == "trac_project_item_get":
        return _project_item(raw)
    if name == "trac_enum_list":
        return {
            "kind": _string(raw.get("kind")),
            "items": [
                {
                    "kind": _string(item.get("kind")),
                    "name": _string(item.get("name")),
                    "value": _text(item.get("value")),
                    "description": _text(item.get("description")),
                }
                for item in raw.get("items", [])
            ],
        }
    if name in ("trac_project_item_create", "trac_project_item_update"):
        item = _project_item(raw)
        if name == "trac_project_item_create":
            item["duplicate"] = bool(raw.get("duplicate"))
        return item
    if name in ("trac_ticket_create", "trac_ticket_update"):
        return {
            "ticket": _ticket(raw["ticket"]),
            "duplicate": bool(raw.get("duplicate")),
            "action": _text(raw.get("action")),
            "action_changes": _action_changes(raw.get("action_changes")),
        }
    if name == "trac_ticket_comment":
        return {
            "ticket": _ticket(raw["ticket"]),
            "duplicate": bool(raw.get("duplicate")),
        }
    if name == "trac_wiki_recent_changes":
        return {
            "changes": [
                {
                    "page": _string(item.get("page")),
                    "version": int(item.get("version") or 0),
                    "time": int(item.get("time") or 0),
                    "author": _text(item.get("author")),
                    "comment": _text(item.get("comment")),
                }
                for item in raw.get("changes", [])
            ],
            "limit": int(raw.get("limit") or 0),
        }
    if name == "trac_wiki_list":
        return {"pages": _strings(raw.get("pages"))}
    if name == "trac_wiki_search":
        return {
            "results": [
                {
                    "page": _string(item.get("page")),
                    "version": int(item.get("version") or 0),
                    "excerpt": _string(item.get("excerpt")),
                }
                for item in raw.get("results", [])
            ]
        }
    if name == "trac_attachment_list":
        return {
            "attachments": [_attachment(item) for item in raw.get("attachments", [])]
        }
    if name == "trac_attachment_upload":
        return {
            "realm": _string(raw.get("realm")),
            "resource": _string(raw.get("resource")),
            "filename": _string(raw.get("filename")),
            "size": _integer_or_none(raw.get("size")),
            "duplicate": bool(raw.get("duplicate")),
        }
    if name == "trac_attachment_get":
        item = _attachment(raw)
        item["content_base64"] = _string(raw.get("content_base64"))
        return item
    if name in ("trac_wiki_get", "trac_wiki_update"):
        return _wiki_page(raw)
    if name == "trac_wiki_history":
        return {
            "history": [
                {
                    "version": int(item.get("version") or 0),
                    "time": int(item.get("time") or 0),
                    "author": _text(item.get("author")),
                    "comment": _text(item.get("comment")),
                }
                for item in raw.get("history", [])
            ]
        }
    raise KeyError("no output normalizer for %s" % name)
