# Security policy

Please report suspected vulnerabilities privately to the repository owner rather than opening a public issue containing exploit details or secrets. Until a dedicated security address is published, use GitHub's private vulnerability reporting feature when enabled.

Never include production Trac data, credentials, tokens, private keys, server inventories, private URLs or personal information in reports or fixtures. The broker is intentionally local and least-privilege; requests for generic shell, SQL, arbitrary Trac paths or `trac-admin` execution are out of scope by design.

## MCP and trusted-local capability boundary

The MCP adapter advertises only the bounded MCP-visible tool registry and must
reject every unadvertised tool name before contacting the broker. It also
validates arguments against the advertised schema and fixes the broker
operation name after validation, so client arguments cannot substitute a
different broker operation.

`trac-mcp-call` additionally exposes an explicit trusted-local registry for
guarded destructive/batch administration and local wiki-file helpers. Those
operations are intentionally not MCP tools. Destructive local requests require
the operation-specific revision/snapshot guard, an idempotency key where
defined, and the exact confirmation value `DELETE`.

The broker independently enforces the server-side admin boundary for destructive,
batch and enum-administration operations using Unix peer credentials. The caller's
numeric UID must appear in `TRAC_MCP_ADMIN_UIDS`; an empty/unset allowlist denies
those operations even when the process can connect to the socket. The MCP adapter
account should normally not be in that allowlist. This is defense in depth in
addition to the adapter's advertised-tool/schema enforcement.

`TRAC_MCP_AUTHOR` is an attribution identity, not the authorization boundary. Workflow evaluation uses broker-local authority so environments do not need to grant that history author broad Trac permissions merely to make MCP/SentinelX workflow operations function consistently.

Treat access to the broker Unix socket as privileged local access. Do not expose
the socket over a network, make it world-writable, or grant it broadly merely
to obtain the local administrative tier. The local CLI's filesystem helpers run
with the calling OS user's existing filesystem permissions; they do not grant
the broker arbitrary filesystem access.
