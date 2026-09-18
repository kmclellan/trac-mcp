# Changelog

## 0.1.0 - 2026-09-18

First public release.

### MCP and Trac capabilities

- constrained Python 3 MCP adapter for explicitly allowlisted Trac environments;
- dual-runtime Trac compatibility broker for Python 2 and Python 3 Trac installations;
- 26 default MCP-visible tools covering tickets, wiki pages, attachments,
  components/milestones/versions, workflow discovery, enums, health and time;
- 12 additional trusted-local tools through `trac-mcp-call` for guarded
  batch/destructive administration and local wiki-file helpers;
- guarded/idempotent ticket, wiki, attachment and project-metadata operations;
- configured Trac workflow actions for ticket creation and guarded updates,
  including dynamic action inputs;
- milestone/version date metadata, including clearing nullable dates;
- local `trac-mcp-call` one-shot JSON request support using the same broker
  transport and schema validation as the MCP adapter;
- conservative local wiki-file format detection/pull/push, with Markdown
  detected and rejected rather than silently converted.

### Security and reliability

- explicit Trac environment allowlisting;
- revision/snapshot guards, bounded batch sizes and bounded attachments;
- explicit `confirm: "DELETE"` plus idempotency for destructive local
  operations;
- destructive/admin tools omitted from the default MCP surface;
- advertised MCP tool names and input schemas enforced before broker access;
- operation-name override attempts rejected;
- one shared schema validator for the MCP adapter and local CLI;
- trusted-local broker administration protected by Unix peer credentials and
  the default-deny `TRAC_MCP_ADMIN_UIDS` allowlist;
- configurable broker socket group through `TRAC_MCP_SOCKET_GROUP`;
- Unix-stream requests read to EOF under a total request-size cap instead of
  assuming one `recv()` contains a complete request;
- no generic shell, SQL, unrestricted `trac-admin`, arbitrary Trac paths or
  generic filesystem access.

### Compatibility and validation

- GitHub Actions validation on Python 3.10 through 3.13;
- disposable integration fixture coverage on Trac 1.4.4 / Python 2.7.18;
- disposable integration fixture coverage on Trac 1.6 / Python 3;
- workflow creation/update, destructive/admin, idempotency, attachment,
  metadata and socket-authorization test paths;
- fixture loader forced to read broker source rather than stale Python 2
  bytecode;
- real Unix-socket authorization testing;
- production deployment validated through 1MCP with Trac increasing from
  19 to 26 MCP-visible tools and no tool removals.

### Documentation and provenance

- generic configuration and systemd examples;
- detailed human/AI-compatible installation and operations documentation;
- security, contribution, provenance and coding-agent policies;
- capability mapping against the MIT-licensed
  `nerpatech/trac-mcp-server` reference project;
- public future-design plan for selectively promoting trusted-local tools to
  MCP if there is sufficient user demand.
