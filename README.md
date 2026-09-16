# Trac MCP

A deliberately constrained Model Context Protocol (MCP) interface for Trac. It exposes bounded ticket, wiki, attachment and project-metadata operations while avoiding generic shell, SQL, filesystem and `trac-admin` access.

## Architecture

The modern Python 3 stdio MCP server talks to a local Unix-domain socket. A legacy compatibility broker can run inside the Python environment that owns an older Trac installation. The MCP-facing process therefore does not need direct access to Trac environment files.

Configuration is explicit and allowlisted. `TRAC_MCP_ENVIRONMENTS` is a comma-separated list of public environment IDs for the MCP server; the legacy broker uses `id=/absolute/trac/path` pairs. `TRAC_MCP_SOCKET` selects the Unix socket. `TRAC_MCP_AUTHOR` selects the Trac history author for broker writes.

## Security model

Environment IDs are allowlisted. Writes use revision/snapshot guards; create/comment/upload operations use idempotency keys. Attachment names and sizes are bounded. There is no generic SQL, shell, arbitrary path, delete, or `trac-admin` tool. Run the broker as a dedicated least-privilege account with filesystem access only to explicitly configured Trac environments.

Do not expose the broker socket directly to untrusted users or networks. Authentication and per-user authorization belong at the MCP gateway/client boundary.

## Current compatibility

The MCP adapter is Python 3. The included `legacy/trac_broker_py2.py` exists for older Trac 1.2/Python 2 deployments and should be treated as a compatibility path. Modern Trac/Python combinations need CI validation before they are claimed as supported.

## Development

Protocol tests are self-contained. The legacy fixture test requires a disposable Trac environment and must never target production. See `SECURITY.md` and `CONTRIBUTING.md` before contributing.

This project is licensed under the MIT License.
