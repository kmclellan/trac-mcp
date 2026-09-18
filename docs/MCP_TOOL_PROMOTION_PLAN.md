# Future design: selectively exposing trusted-local tools through MCP

> **Status:** future / feedback-driven development. This is a scoped design, not a current implementation commitment. The default MCP surface remains intentionally conservative. This mechanism should be developed only if users have a clear need for it.

## Why this may be useful

`trac-mcp` currently has two capability tiers:

- **MCP-visible tools**: the bounded default surface intended for ordinary MCP clients.
- **Trusted-local tools**: additional batch, destructive/admin and local wiki-file operations available through `trac-mcp-call`, for trusted local automation such as SentinelX.

Some installations may eventually want to expose selected trusted-local tools to MCP. The goal is to make that possible without turning the MCP adapter into a fully trusted local administrator.

A simple switch such as “enable all local tools” is not sufficient. Broker-side trusted-local operations are protected by Unix peer UID. Adding the MCP adapter UID to the unrestricted admin allowlist would give it the entire local-admin tier rather than only the tools an administrator deliberately selected.

The proposed design therefore uses an **explicit per-tool promotion policy enforced by both the MCP adapter and the broker**.

## Design principles

Any future implementation should preserve these properties:

- no change to the default MCP surface unless an administrator opts in;
- no wildcard that automatically exposes future tools;
- explicit per-tool promotion;
- broker-side enforcement as well as MCP-adapter enforcement;
- full trusted-local/SentinelX authority remains separate from selectively promoted MCP authority;
- existing revision/snapshot guards, idempotency, batch limits and explicit destructive confirmation remain mandatory;
- no generic shell, SQL, unrestricted `trac-admin`, arbitrary Trac environment paths or generic filesystem access;
- invalid policy should fail closed;
- removing the policy should restore the conservative default after restart.

## Proposed policy file

A versioned JSON policy is the simplest first implementation because JSON is available in Python 2.7 and all supported Python 3 runtimes without another parser dependency.

Example configuration:

```text
TRAC_MCP_TOOL_POLICY=/etc/trac-mcp/tool-policy.json
```

Example policy:

```json
{
  "version": 1,
  "mcp": {
    "promote": [
      "trac_ticket_batch_create",
      "trac_ticket_batch_update"
    ]
  }
}
```

For version 1:

- tool names must be explicit;
- no `*`, “all”, or equivalent wildcard;
- unknown or non-promotable tools should make policy validation fail;
- duplicate or conflicting entries should be rejected;
- no policy, or an empty promotion list, must produce today's default MCP surface;
- the policy should be loaded at process startup; changing it should require a deliberate adapter/broker restart rather than a runtime MCP mutation.

## Canonical tool registry

The current MCP-visible and trusted-local definitions should eventually be represented by one canonical tool catalogue.

Each tool definition should record at least:

- tool name and description;
- input schema;
- default exposure: MCP or trusted-local;
- execution mode: broker-backed or adapter-local;
- broker operation name where applicable;
- risk class such as read-only, write, destructive or filesystem;
- whether the tool is promotable;
- suitable MCP annotations where supported.

The effective MCP surface would be:

```text
default MCP tools + explicitly promoted tools
```

`trac-mcp-call` would continue to expose the complete trusted-local set to appropriately authorized local automation.

## Broker authorization

Full trusted-local administration and selective MCP promotion should use different identities.

The existing setting:

```text
TRAC_MCP_ADMIN_UIDS=...
```

should continue to identify fully trusted local administrators such as SentinelX.

A future setting could identify MCP-adapter peers separately:

```text
TRAC_MCP_ADAPTER_UIDS=...
```

For broker-side admin operations:

1. a peer UID in `TRAC_MCP_ADMIN_UIDS` retains the existing full trusted-local authority;
2. a peer UID in `TRAC_MCP_ADAPTER_UIDS` may execute only the broker operations corresponding to tools explicitly promoted by the policy;
3. all other peers are denied.

The MCP adapter should **not** be added to `TRAC_MCP_ADMIN_UIDS` merely to make one local tool MCP-visible.

This gives defense in depth: an adapter bug or guessed operation name still cannot invoke an unpromoted admin operation at the broker.

## Filesystem-backed wiki helpers

The local wiki-file tools need stricter treatment because they access the filesystem of the MCP adapter process.

They should require an additional explicit filesystem sandbox before they can be promoted.

Conceptual example:

```json
{
  "version": 1,
  "mcp": {
    "promote": [
      "trac_wiki_file_detect_format"
    ],
    "filesystem": {
      "enabled": true,
      "roots": [
        "/srv/trac-mcp-files"
      ]
    }
  }
}
```

Requirements should include:

- filesystem promotion is disabled unless explicitly enabled;
- at least one allowed root is required;
- every input/output path must resolve inside an allowed root;
- `..` traversal and symlink escapes must be rejected;
- atomic-write behavior must be preserved;
- normal OS permissions remain an additional boundary;
- no generic filesystem browse/read/write tool is introduced.

It may be preferable to support separate read and write roots rather than a single root list.

## Administrator UX

A dedicated read-only command such as `trac-mcp-policy` would make this safer to configure.

Useful commands could include:

```text
trac-mcp-policy validate /etc/trac-mcp/tool-policy.json
trac-mcp-policy show-effective /etc/trac-mcp/tool-policy.json
trac-mcp-policy list-promotable
```

It should be able to show:

- default MCP tools;
- trusted-local/promotable tools;
- risk and execution class;
- effective MCP exposure under a policy;
- exact broker operations an MCP-adapter peer would gain;
- validation errors with clear explanations.

Version 1 should be inspection/validation only. It should not silently edit the policy or enable tools.

## MCP metadata

If promoted tools are advertised over MCP, suitable tool annotations should be added where the protocol/client supports them, for example:

- `readOnlyHint`;
- `destructiveHint`;
- `idempotentHint`;
- `openWorldHint`.

These annotations are guidance for clients and users, not a security boundary.

Descriptions for promoted destructive tools should clearly state their confirmation, revision and idempotency requirements.

## Development plan

### Phase A — registry and policy foundation

1. Introduce a canonical tool-definition module shared by the MCP server and local CLI.
2. Add exposure, execution, risk and promotability metadata.
3. Implement a strict versioned JSON policy parser/validator.
4. Build the effective MCP registry from defaults plus explicit promotion.
5. Preserve exact no-policy behavior.
6. Add read-only policy inspection/validation commands.

### Phase B — broker-backed promotion

1. Introduce a separate MCP-adapter UID allowlist.
2. Make the broker consume the same promotion policy.
3. Map promoted tool names to exact broker operations.
4. Keep full admin UIDs separate from selective adapter UIDs.
5. Validate first with a relatively benign broker-backed tool such as batch ticket creation.
6. Validate a destructive tool separately.
7. Prove that every unpromoted admin operation remains denied to the adapter.

### Phase C — filesystem-backed promotion

1. Share/extract the file-helper execution code.
2. Add explicit filesystem sandbox policy.
3. Implement canonical root-containment and symlink-escape checks.
4. Test read-only format detection first.
5. Test push/pull in disposable sandbox roots.
6. Keep filesystem tools unavailable unless the additional filesystem policy is valid.

### Phase D — documentation and rollout

1. Update README, SECURITY, examples and capability documentation.
2. Add safe example policies.
3. Document numeric UID discovery and separation of full-admin versus adapter identities.
4. Document restart and rollback procedures.
5. Add upgrade notes confirming existing installations remain unchanged without policy.
6. Log the effective promoted tool names/risk classes at startup without leaking private paths or credentials.

## Acceptance criteria

Before this feature would be considered ready:

- no policy -> the existing default MCP/local split is unchanged;
- empty policy -> same;
- explicitly promoted broker tool appears in MCP `tools/list` and is callable;
- unpromoted local tool remains absent and rejected;
- unknown or invalid policy fails closed;
- MCP adapter UID cannot execute unpromoted broker admin operations;
- full trusted-local admin UID retains its independent authority;
- destructive promoted calls still require exact confirmation plus revision/idempotency controls;
- operation-name override protection remains intact;
- batch and attachment bounds remain intact;
- Trac 1.6/Python 3 fixture passes;
- Trac 1.4.4/Python 2.7 broker fixture passes;
- filesystem promotion without valid sandbox policy is rejected;
- path traversal and symlink escapes are rejected;
- allowed sandbox paths work;
- removing the policy and restarting restores the conservative default.

## Rollout approach

If there is sufficient user interest:

1. implement the feature with no-policy behavior unchanged;
2. test against disposable Trac 1.6 and 1.4.4 environments;
3. release the policy/documentation support without enabling any promotion by default;
4. verify the normal default MCP surface after upgrade;
5. opt in one relatively benign broker-backed tool first;
6. consider destructive tools only after that succeeds;
7. treat filesystem-backed promotion as a separate explicit rollout.

Rollback should be simple: remove/revert the policy and restart the adapter/broker. The safe default surface remains compiled into the package.

## Current decision

This feature is **not currently scheduled for development**.

The design is documented so GitHub users can review it and provide feedback. If there is clear demand for selectively promoting trusted-local tools to MCP, the plan above provides a path to implement it without weakening the project's default security model.
