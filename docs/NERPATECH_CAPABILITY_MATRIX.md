# nerpatech/trac-mcp-server capability mapping

This document records the capability review performed on 18 September 2026
against `nerpatech/trac-mcp-server` at commit
`59fd236f14b4f291f032d8f739d651ea49d35e0c`.

Upstream is licensed under the MIT License (copyright 2026 nerpa.tech), which
is compatible with this project's MIT licence. The expansion described here
was implemented independently against Trac's model APIs using the upstream
tool catalogue and documentation as a requirements/reference source. No
upstream implementation source was copied into this change.

The projects expose different shapes. Upstream publishes 43 separately named
tools. This project deliberately consolidates related operations (for example,
ticket/wiki attachment operations share one attachment API, and
component/milestone/version operations share one project-item API). Therefore
tool-name counts are not directly comparable. The current local shape is 26
MCP-visible tools plus 12 additional SentinelX/local-only tools (38 named
tools total) covering the 43 upstream capability areas through consolidation.

## Exposure policy

- **MCP-visible**: bounded, generally benign/read-oriented operations and
  already-established guarded writes.
- **SentinelX/local CLI only**: destructive operations, batch mutation, enum
  administration and local-filesystem wiki helpers. These are available
  through `trac-mcp-call` but are not advertised by the MCP server.
- The MCP adapter enforces the split: unadvertised tool names are rejected,
  arguments are validated against the advertised schema before broker access,
  and the broker operation name cannot be overridden by client arguments.
- Local destructive operations require an explicit `confirm: "DELETE"`,
  revision/snapshot guards where applicable, and idempotency keys.
- Batch ticket operations are capped at 50 and are intentionally per-item:
  successes and failures are returned separately rather than rolling the
  entire batch back when one item fails.
- Broker-side local admin operations are also protected by Unix peer UID: the
  caller's UID must appear in `TRAC_MCP_ADMIN_UIDS`. The default empty allowlist
  disables these operations even for processes that can open the broker socket.
- Local wiki file helpers operate on the caller's filesystem, so they are
  deliberately not exposed over MCP. Markdown is detected but not silently
  converted; push accepts TracWiki only unless the caller explicitly asserts
  that the source is already TracWiki.

## Capability matrix

| Upstream tool | Local equivalent | Exposure | Notes |
| --- | --- | --- | --- |
| `ticket_search` | `trac_ticket_query` | MCP | Trac query syntax; bounded results |
| `ticket_get` | `trac_ticket_get` | MCP | Includes guarded change token |
| `ticket_create` | `trac_ticket_create` | MCP | Idempotent; applies the configured creation workflow and broker reporter identity; optional creation action/action inputs |
| `ticket_update` | `trac_ticket_update` | MCP | Revision guarded; optional idempotency; status/resolution require a discovered workflow action/action inputs rather than direct field edits |
| `ticket_delete` | `trac_ticket_delete` | SentinelX | Revision + DELETE confirmation + idempotency |
| `ticket_changelog` | `trac_ticket_timeline` | MCP | Chronological comments/field changes |
| `ticket_fields` | `trac_ticket_fields` | MCP | Standard/custom field definitions |
| `ticket_actions` | `trac_ticket_actions` | MCP | Current workflow actions and action input names |
| `ticket_batch_create` | `trac_ticket_batch_create` | SentinelX | Max 50, per-item idempotency |
| `ticket_batch_delete` | `trac_ticket_batch_delete` | SentinelX | Max 50, per-item revisions + confirmation |
| `ticket_batch_update` | `trac_ticket_batch_update` | SentinelX | Max 50, per-item revisions/idempotency |
| `ticket_attachment_put` | `trac_attachment_upload` | MCP | Generic ticket/wiki realm; guarded and idempotent |
| `ticket_attachment_get` | `trac_attachment_get` | MCP | Generic ticket/wiki realm; bounded bytes |
| `ticket_attachment_list` | `trac_attachment_list` | MCP | Generic ticket/wiki realm |
| `ticket_attachment_delete` | `trac_attachment_delete` | SentinelX | Target revision + confirmation + idempotency |
| `ticket_component_create` | `trac_project_item_create(kind=component)` | MCP | Idempotent |
| `ticket_component_list` | `trac_project_item_list(kind=component)` | MCP | Bounded |
| `ticket_component_delete` | `trac_project_item_delete(kind=component)` | SentinelX | Snapshot + confirmation + idempotency |
| `ticket_enum_create` | `trac_enum_create` or project-item version create | SentinelX/MCP | Priority/resolution/severity/type are local-only enums; versions use project-item API |
| `ticket_enum_list` | `trac_enum_list` or project-item version list | MCP | Includes workflow-derived status values |
| `ticket_enum_delete` | `trac_enum_delete` or project-item version delete | SentinelX | Status is workflow-derived and intentionally not mutable |
| `wiki_get` | `trac_wiki_get` | MCP | Stored TracWiki |
| `wiki_search` | `trac_wiki_search` | MCP | Bounded excerpts |
| `wiki_create` | `trac_wiki_update(expected_version=0)` | MCP | Same guarded API handles create/update |
| `wiki_update` | `trac_wiki_update` | MCP | Revision guarded |
| `wiki_delete` | `trac_wiki_delete` | SentinelX | Revision + confirmation + idempotency |
| `wiki_recent_changes` | `trac_wiki_recent_changes` | MCP | Latest revision per page, bounded |
| `wiki_get_history` | `trac_wiki_history` | MCP | Version history |
| `wiki_file_push` | `trac_wiki_file_push` | SentinelX | Local filesystem; TracWiki only; Markdown is rejected rather than auto-converted |
| `wiki_file_pull` | `trac_wiki_file_pull` | SentinelX | Atomic local raw-TracWiki write |
| `wiki_file_detect_format` | `trac_wiki_file_detect_format` | SentinelX | Extension + conservative content heuristic |
| `wiki_attachment_put` | `trac_attachment_upload` | MCP | Generic ticket/wiki realm |
| `wiki_attachment_get` | `trac_attachment_get` | MCP | Generic ticket/wiki realm |
| `wiki_attachment_list` | `trac_attachment_list` | MCP | Generic ticket/wiki realm |
| `wiki_attachment_delete` | `trac_attachment_delete` | SentinelX | Target revision + confirmation + idempotency |
| `milestone_list` | `trac_project_item_list(kind=milestone)` | MCP | Can exclude completed milestones |
| `milestone_get` | `trac_project_item_get(kind=milestone)` | MCP | Snapshot data |
| `milestone_create` | `trac_project_item_create(kind=milestone)` | MCP | Idempotent; due/completed timestamps use Trac microseconds since epoch |
| `milestone_update` | `trac_project_item_update(kind=milestone)` | MCP | Snapshot guarded; due/completed timestamps are nullable Trac microseconds |
| `milestone_delete` | `trac_project_item_delete(kind=milestone)` | SentinelX | Snapshot + confirmation + idempotency |
| `ping` | `trac_ping` | MCP | Broker/Trac/project/version health |
| `get_server_time` | `trac_server_time` | MCP | UTC + Unix timestamp |
| `list_instances` | `trac_environments` | MCP | Explicit allowlist only; no host discovery |

## Intentional differences

The local broker does not discover arbitrary Trac environments. Environment
IDs remain explicitly allowlisted, which is a deliberate security boundary.

The local file helpers do not silently convert Markdown to TracWiki. Upstream's
converter is capable but substantially larger and adds parser/dependency
surface. For this first expansion, Markdown is detected and rejected so an
automation cannot silently alter documentation semantics. A future converter
can be reviewed separately with explicit provenance, dependency and fidelity
tests.

Destructive operations are deliberately absent from the MCP tool list even
though SentinelX can invoke them through the same broker using
`trac-mcp-call`. This preserves one implementation/security boundary while
allowing a more capable trusted local operations path.
