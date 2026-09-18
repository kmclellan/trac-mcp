# Changelog

## Unreleased

- expand the constrained broker to cover the capability areas reviewed from
  the MIT-licensed `nerpatech/trac-mcp-server` reference project;
- add MCP-visible broker health/server time, ticket field/workflow discovery,
  project-item lists, enum lists and recent wiki changes;
- add a separate `trac-mcp-call` local-only tier for guarded deletion, batch
  ticket mutation, enum administration and local wiki-file helpers;
- support configured Trac workflow actions for ticket creation and guarded
  updates, including dynamic action inputs, while preventing direct
  status/resolution edits that bypass the workflow state machine;
- support milestone/version date metadata, including clearing nullable dates;
- require explicit `confirm: "DELETE"`, revision/snapshot checks and
  idempotency for destructive local operations;
- keep destructive/admin tools out of the MCP tool list and reject
  unadvertised tool names, invalid arguments and operation-name overrides
  before broker access;
- share one schema validator between the MCP adapter and local CLI;
- enforce the broker local-admin tier with Unix peer credentials and the
  default-deny `TRAC_MCP_ADMIN_UIDS` allowlist;
- replace the hard-coded broker socket group with configurable
  `TRAC_MCP_SOCKET_GROUP`;
- read Unix-stream broker requests to EOF under the existing total-size cap
  rather than assuming one `recv()` contains the complete request;
- detect and reject Markdown wiki-file pushes rather than silently converting
  documentation without a separately reviewed converter;
- expand disposable broker fixture coverage for Trac 1.4.4/Python 2.7 and
  Trac 1.6/Python 3, including workflow, destructive/admin, idempotency and
  socket-authorization paths;
- force the fixture loader to read broker source rather than silently accepting
  stale Python 2 bytecode.

## 0.1.0 - 2026-09-16

Initial public-release candidate:

- constrained Python 3 MCP adapter for explicitly allowlisted Trac environments;
- dual-runtime Trac compatibility broker for Python 2 and Python 3 Trac installations;
- guarded/idempotent ticket, wiki, attachment and project-metadata operations;
- generic configuration and systemd examples;
- protocol and disposable compatibility-broker fixture tests;
- GitHub Actions validation on Python 3.10 through 3.13;
- detailed human/AI-compatible installation and operations documentation;
- security, contribution, provenance and coding-agent policies;
- local `trac-mcp-call` one-shot CLI that validates JSON requests against the
  published MCP tool schemas and reuses the constrained broker transport for
  local recovery/automation;
- Trac 1.4.4/Python 2.7.18 integration validation, including compatibility fixes for wiki saves and ticket change timestamps;
- Trac 1.6/Python 3.9.2 integration validation, including Python 3 text/byte compatibility, attachment byte streams, and four-field wiki-history support.
