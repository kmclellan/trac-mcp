"""MCP output schemas for the default Trac tool surface.

The currently supported MCP revisions through 2025-11-25 require structured
tool output to be an object, so every schema here has an object root.
"""

def obj(properties=None, required=None, additional=False):
    schema = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": additional,
    }
    if required:
        schema["required"] = required
    return schema


STRING = {"type": "string"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}
NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_INTEGER = {"type": ["integer", "null"]}
ANY = {}

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
    },
    [
        "id",
        "changed",
        "summary",
        "description",
        "status",
        "type",
        "priority",
        "milestone",
        "component",
        "owner",
        "reporter",
        "keywords",
        "resolution",
    ],
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
    },
    ["kind", "name", "description"],
)

PROJECT_ITEM_CREATED = obj(
    dict(PROJECT_ITEM["properties"], duplicate=BOOLEAN),
    ["kind", "name", "description", "duplicate"],
)

ENUM_ITEM = obj(
    {
        "kind": {
            "type": "string",
            "enum": ["priority", "resolution", "severity", "status", "type"],
        },
        "name": STRING,
        "value": ANY,
        "description": NULLABLE_STRING,
    },
    ["kind", "name", "value", "description"],
)

WORKFLOW_ACTION = obj(
    {
        "name": STRING,
        "label": STRING,
        "hint": STRING,
        "input_fields": {"type": "array", "items": STRING},
    },
    ["name", "label", "hint", "input_fields"],
)

TICKET_FIELD = obj(
    {
        "name": STRING,
        "type": STRING,
        "label": STRING,
        "custom": BOOLEAN,
        "optional": BOOLEAN,
        "options": {"type": "array", "items": ANY},
        "value": ANY,
        "format": STRING,
        "max_size": INTEGER,
    },
    ["name", "type", "label"],
    additional=True,
)

ATTACHMENT = obj(
    {
        "realm": {"type": "string", "enum": ["ticket", "wiki"]},
        "resource": STRING,
        "filename": STRING,
        "size": INTEGER,
        "author": NULLABLE_STRING,
        "description": NULLABLE_STRING,
    },
    ["realm", "resource", "filename", "size", "author", "description"],
)

WIKI_PAGE = obj(
    {
        "page": STRING,
        "version": INTEGER,
        "text": STRING,
        "author": NULLABLE_STRING,
        "comment": NULLABLE_STRING,
    },
    ["page", "version", "text", "author", "comment"],
)

TICKET_MUTATION = obj(
    {
        "ticket": TICKET,
        "duplicate": BOOLEAN,
        "action": {"type": ["string", "null"]},
        "action_changes": {"type": "object"},
    },
    ["ticket", "duplicate"],
)

OUTPUT_SCHEMAS = {
    "trac_environments": obj(
        {"environments": {"type": "array", "items": STRING}},
        ["environments"],
    ),
    "trac_ping": obj(
        {
            "environment": STRING,
            "project_name": STRING,
            "trac_version": STRING,
        },
        ["environment", "project_name", "trac_version"],
    ),
    "trac_server_time": obj(
        {"unix_timestamp": INTEGER, "iso_utc": STRING},
        ["unix_timestamp", "iso_utc"],
    ),
    "trac_ticket_get": TICKET,
    "trac_ticket_query": obj(
        {"tickets": {"type": "array", "items": TICKET}},
        ["tickets"],
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
                        "old": ANY,
                        "new": ANY,
                        "permanent": BOOLEAN,
                    },
                    ["time", "author", "field", "old", "new", "permanent"],
                ),
            },
        },
        ["ticket_id", "timeline"],
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
        },
        [
            "types",
            "priorities",
            "components",
            "milestones",
            "versions",
            "resolutions",
            "owners",
        ],
    ),
    "trac_ticket_fields": obj(
        {"fields": {"type": "array", "items": TICKET_FIELD}},
        ["fields"],
    ),
    "trac_ticket_actions": obj(
        {
            "ticket_id": INTEGER,
            "authname": STRING,
            "actions": {"type": "array", "items": WORKFLOW_ACTION},
        },
        ["ticket_id", "authname", "actions"],
    ),
    "trac_project_item_list": obj(
        {
            "kind": {"type": "string", "enum": ["component", "milestone", "version"]},
            "items": {"type": "array", "items": PROJECT_ITEM},
            "total": INTEGER,
        },
        ["kind", "items", "total"],
    ),
    "trac_project_item_get": PROJECT_ITEM,
    "trac_enum_list": obj(
        {
            "kind": {
                "type": "string",
                "enum": ["priority", "resolution", "severity", "status", "type"],
            },
            "items": {"type": "array", "items": ENUM_ITEM},
        },
        ["kind", "items"],
    ),
    "trac_project_item_create": PROJECT_ITEM_CREATED,
    "trac_project_item_update": PROJECT_ITEM,
    "trac_ticket_create": TICKET_MUTATION,
    "trac_ticket_update": TICKET_MUTATION,
    "trac_ticket_comment": obj(
        {"ticket": TICKET, "duplicate": BOOLEAN},
        ["ticket", "duplicate"],
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
                    },
                    ["page", "version", "time", "author", "comment"],
                ),
            },
            "limit": INTEGER,
        },
        ["changes", "limit"],
    ),
    "trac_wiki_list": obj(
        {"pages": {"type": "array", "items": STRING}},
        ["pages"],
    ),
    "trac_wiki_search": obj(
        {
            "results": {
                "type": "array",
                "items": obj(
                    {"page": STRING, "version": INTEGER, "excerpt": STRING},
                    ["page", "version", "excerpt"],
                ),
            }
        },
        ["results"],
    ),
    "trac_attachment_list": obj(
        {"attachments": {"type": "array", "items": ATTACHMENT}},
        ["attachments"],
    ),
    "trac_attachment_upload": obj(
        {
            "realm": {"type": "string", "enum": ["ticket", "wiki"]},
            "resource": STRING,
            "filename": STRING,
            "size": INTEGER,
            "duplicate": BOOLEAN,
        },
        ["realm", "resource", "filename", "duplicate"],
    ),
    "trac_attachment_get": obj(
        dict(ATTACHMENT["properties"], content_base64=STRING),
        [
            "realm",
            "resource",
            "filename",
            "size",
            "author",
            "description",
            "content_base64",
        ],
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
                    },
                    ["version", "time", "author", "comment"],
                ),
            }
        },
        ["history"],
    ),
    "trac_wiki_update": WIKI_PAGE,
}
