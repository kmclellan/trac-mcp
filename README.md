# Trac MCP

A deliberately constrained Model Context Protocol (MCP) interface for Trac. It lets MCP clients work with explicitly approved Trac environments without exposing generic shell, SQL, filesystem, `trac-admin`, or destructive administration access.

This README is intended to be usable by both people and AI coding/operations agents. Commands state their assumptions; do not substitute production paths, users, or permissions without reviewing the security consequences.

## Status

The current public release is `v0.1.2` (18 September 2026). The Python 3 MCP adapter and protocol tests are validated on Python 3.10 through 3.13 in GitHub Actions. The default surface exposes 26 MCP tools, with 12 additional trusted-local tools available through `trac-mcp-call`. Every MCP-visible tool declares a strict object-root `outputSchema`; successful calls return normalized `structuredContent` that satisfies that schema while retaining the original broker JSON as text for backward compatibility. `legacy/trac_broker_py2.py` is the Trac compatibility broker; despite the historical filename, it supports both Python 2 and Python 3 Trac runtimes.

The compatibility broker has been integration-tested with **Trac 1.4.4 on Python 2.7.18** and **Trac 1.6 on Python 3.9.2**. The Trac 1.4.4 validation used a disposable copy for bounded writes plus read-only checks against the staged environment. The Trac 1.6 validation used a disposable copy of the upgraded staged environment for bounded writes and a full adapter-to-broker Unix-socket test. Direct API access to the staged Trac 1.6 environment was intentionally not forced because the test account does not have the write permission that Trac requires for its SQLite environment.

## What it does

The MCP-facing Python 3 process communicates over a local Unix-domain socket with a broker that owns the actual Trac API access. This separates the modern MCP runtime from an older Trac runtime and avoids giving the MCP process direct filesystem access to Trac environments.

The interface is deliberately bounded. Environment IDs are explicitly allowlisted; guarded writes use revision/snapshot checks; creation/comment/upload operations use idempotency keys; and attachment names and sizes are bounded. Ticket status/resolution transitions must use configured Trac workflow actions rather than direct field edits. The **MCP-visible surface** has no destructive/delete tools. A separate trusted local `trac-mcp-call` tier provides explicitly guarded deletion/batch administration and local wiki-file helpers without adding generic SQL, shell, arbitrary Trac paths, or arbitrary `trac-admin` access.

A possible future mechanism for administrators to **selectively promote trusted-local tools into MCP** is scoped in [`docs/MCP_TOOL_PROMOTION_PLAN.md`](docs/MCP_TOOL_PROMOTION_PLAN.md). It is not currently scheduled for implementation; the design is published for GitHub feedback and can be developed if there is sufficient user interest.

## Architecture

```text
MCP client / gateway
        |
        | stdio MCP
        v
Python 3 trac-mcp adapter
        |
        | local Unix-domain socket
        v
Trac compatibility broker
        |
        | Trac Python API
        v
explicitly allowlisted Trac environment(s)
```

The socket is a local trust boundary. Do not expose it directly to a network or to untrusted local users. Normal MCP authentication/authorization belongs at the client/gateway boundary; the broker additionally enforces peer-UID authorization for its trusted local-admin operation set. The broker's `TRAC_MCP_AUTHOR` value is used for Trac history/workflow attribution only; workflow evaluation intentionally uses the broker's trusted authority rather than requiring that attribution name to hold matching Trac login permissions in every environment.

## Requirements

### MCP adapter

- Python 3.10 or newer.
- A Unix-like system when using the supplied Unix-socket broker design.
- Local access to the configured broker Unix socket.
- `pip` or another PEP 517-capable Python installer for package installation.

The adapter does **not** require direct access to the Trac environment directory.

### Compatibility broker

The supplied broker runs inside the Python runtime used by the target Trac installation. It has been validated with Trac 1.4.4/Python 2.7.18 and Trac 1.6/Python 3.9.2. The historical filename `legacy/trac_broker_py2.py` is retained for compatibility, but the source is dual-runtime.

It requires:

- the Python interpreter used by the target Trac installation;
- the Trac Python package importable by that interpreter;
- filesystem/database permissions required by Trac for only the environments you explicitly configure;
- permission to create and serve the configured Unix socket.

Run the broker as a dedicated least-privilege account. Do not run it as root merely to bypass permissions. For SQLite-backed environments, note that Trac itself requires the runtime account to have write access to the database file and its containing directory, even for operations that are logically read-only.

## Quick start for development

These commands exercise the MCP adapter without connecting to a production Trac installation.

```sh
git clone <repository-url>
cd trac-mcp
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
python -m unittest tests.test_trac_mcp_protocol tests.test_trac_mcp_call
```

Expected result: the adapter/protocol and local-CLI test suites report `OK`.

To verify the installed console entry point can start:

```sh
printf '' | trac-mcp
```

An empty standard input causes it to exit; this is a startup/package check, not an end-to-end Trac test.

If `python3 -m venv` reports that `ensurepip` is unavailable, install your operating system's Python venv package using its normal package-management procedure, then recreate the virtual environment. Do not work around this by running project development as root.

## Installation

### 1. Install the Python 3 adapter

For a system or service deployment, choose an installation location appropriate to your operating system. For development, use a virtual environment as shown above.

From a checked-out release:

```sh
python3 -m pip install .
```

Verify:

```sh
command -v trac-mcp
```

### 2. Configure the adapter

The adapter understands these environment variables:

| Variable | Meaning | Example |
| --- | --- | --- |
| `TRAC_MCP_SOCKET` | Unix socket used to reach the broker | `/run/trac-mcp/trac.sock` |
| `TRAC_MCP_ENVIRONMENTS` | Comma-separated public environment IDs exposed through MCP | `example,docs` |
| `TRAC_MCP_AUTHOR` | Trac history/workflow attribution identity (not an authorization principal) | `MCP` |

Start from `examples/trac-mcp.env.example`. Environment IDs should be stable public labels; they do not need to reveal filesystem paths or host information.

### 3. Configure the compatibility broker

The broker's `TRAC_MCP_ENVIRONMENTS` has a different form because it maps public IDs to local Trac paths:

```text
TRAC_MCP_ENVIRONMENTS=example=/srv/trac/example,docs=/srv/trac/docs
```

Only list environments that MCP is intended to reach. Use absolute paths. The public adapter should expose only the corresponding IDs (`example,docs`), not these paths.

Broker-specific settings are:

| Variable | Meaning | Default |
| --- | --- | --- |
| `TRAC_MCP_SOCKET` | Unix socket created by the broker | `/run/trac-mcp/trac.sock` |
| `TRAC_MCP_SOCKET_GROUP` | Optional group name/numeric GID assigned to the socket | unchanged/inherited when empty |
| `TRAC_MCP_ENVIRONMENTS` | Comma-separated `id=/absolute/path` allowlist | example placeholder |
| `TRAC_MCP_AUTHOR` | Trac history/workflow attribution identity | `MCP` |
| `TRAC_MCP_ADMIN_UIDS` | Comma-separated numeric OS UIDs allowed to invoke the trusted local-admin broker operations | empty (local-admin broker operations disabled) |

If `TRAC_MCP_SOCKET_GROUP` is set, the broker OS account must be permitted to
assign that group to the socket (normally by being a member of the group), and
the adapter account must have the intended socket access. Do not make the
socket world-writable to avoid configuring this relationship correctly.

If the trusted local admin tier is required, set `TRAC_MCP_ADMIN_UIDS` in the **broker** environment to a comma-separated list of numeric OS UIDs. The default empty/unset value disables broker-side local admin operations. Obtain a service account's numeric UID using your operating system's normal account tools; do not put usernames into this numeric setting. The MCP adapter UID should normally remain absent from this allowlist.

Start from `examples/trac-broker.env.example`.

### 4. Run the broker

A generic systemd example is provided at `examples/systemd/trac-mcp-broker.service.example`. It deliberately uses placeholder installation paths and a generic `trac` service account. Review and adapt it rather than copying it blindly.

Before enabling a service, verify manually that:

1. the configured interpreter imports Trac;
2. the service account can access each intended Trac environment and no unintended environment;
3. the socket directory is writable by the broker and accessible by the adapter;
4. any configured `TRAC_MCP_SOCKET_GROUP` can actually be assigned by the broker account and grants only the intended local clients access;
5. `TRAC_MCP_ADMIN_UIDS` contains only explicitly trusted local automation UIDs (and normally not the MCP adapter UID);
6. the environment file is not writable by untrusted users.

Then use your operating system's normal systemd workflow to install, enable, start, and inspect the service. System-level installation generally requires administrator privileges; source development and Git operations do not.

The broker imports one Trac runtime per process. During a rolling Trac upgrade, do not assume one broker can safely serve a mixed fleet where some environments still require an older Trac runtime and others have already moved to a newer one. Either keep MCP access paused until the exposed environments have moved together, explicitly validate the mixed state, or run separately isolated broker instances for different Trac runtimes.

The effective Trac runtime is the combination of the Python executable and its import environment. A deployment may use a dedicated virtual environment, or an isolated package tree supplied through `PYTHONPATH` or an equivalent mechanism. Verify the exact service environment, not merely the interpreter pathname: the broker process itself should report/import the intended Trac version before production access is reopened.

### 5. Connect an MCP client or gateway

Configure the MCP client to execute the installed `trac-mcp` command using stdio and supply the adapter environment variables. Exact configuration syntax varies between MCP clients, so this project does not provide a client-specific JSON fragment that might become stale.

The MCP process should run as an unprivileged account that can connect to the broker socket but does not need direct Trac filesystem access.

The adapter also publishes MCP server instructions identifying this interface as the preferred application-level route for routine Trac administration (tickets, wiki pages, attachments and project metadata). Those instructions distinguish application administration from host/infrastructure work such as Trac installation, upgrades, service configuration, backups, filesystem permissions and broker deployment/repair, and explicitly discourage direct database writes for routine administration. MCP clients and aggregators that expose server instructions can use this metadata when choosing between overlapping management tools.


### Local one-shot CLI

Installations that already expose the constrained broker socket can also use
`trac-mcp-call` for one bounded operation without running an MCP client. The
CLI reuses the same broker transport and all MCP-visible schemas, and also has a
separate local-only registry for trusted administrative operations that are
intentionally not advertised over MCP.

The local-only tier includes guarded destructive/batch operations and wiki
file helpers. It still does not expose generic shell, SQL, arbitrary Trac
environment paths, or arbitrary broker-side filesystem access. Local file
helpers read/write files as the calling OS user before/after invoking bounded
wiki broker operations.

Batch ticket operations are deliberately **per-item, not transactional across
the whole batch**. Up to 50 items are attempted independently and the response
separates successful and failed items. Each mutation retains its own
revision/idempotency checks. Callers that require all-or-nothing behavior
should not use the batch helpers.

A request is a JSON object containing an MCP tool name and its arguments:

```json
{
  "tool": "trac_ticket_get",
  "arguments": {
    "environment": "example",
    "ticket_id": 7
  }
}
```

Run it from a file:

```sh
trac-mcp-call request.json
```

or from standard input:

```sh
printf '%s\n' '{"tool":"trac_environments","arguments":{}}' | trac-mcp-call
```

The local process must have permission to connect to the configured broker
socket and must use the same `TRAC_MCP_SOCKET` and `TRAC_MCP_ENVIRONMENTS`
configuration as the adapter. Do not make the socket world-writable merely to
use this helper. A deployment may grant a specific automation account access
to the broker socket, but that is a local security decision and should be
narrower than granting direct Trac filesystem/database access.

Broker-side destructive/batch/enum administration is additionally protected by
Unix peer credentials. Configure `TRAC_MCP_ADMIN_UIDS` with the numeric UID(s)
of trusted local automation accounts; if it is empty or unset, those broker
operations fail closed. Do **not** add the MCP adapter account to this allowlist
merely for convenience. Linux peer credentials are supported directly; on
other Unix platforms the runtime must expose an equivalent peer-credential API
or local-admin operations remain unavailable.

`trac-mcp-call` validates every request against either the MCP-visible schema
or the explicit local-only schema before dispatch. Guarded writes retain the
normal revision/snapshot and idempotency requirements; destructive operations
also require `confirm: "DELETE"`.

Inspect the split explicitly:

```sh
trac-mcp-call --list-mcp-tools
trac-mcp-call --list-local-tools
trac-mcp-call --list-tools
```

The local wiki file helpers detect Markdown vs TracWiki, but Markdown is not
silently converted on push. This is deliberate: automatic conversion can alter
documentation semantics and is deferred until a separately reviewed converter
and fidelity test suite are adopted.

The capability/exposure mapping against the 43-tool reference project
`nerpatech/trac-mcp-server` is documented in
[`docs/NERPATECH_CAPABILITY_MATRIX.md`](docs/NERPATECH_CAPABILITY_MATRIX.md).

## Configuration rules

- Keep the adapter's public environment-ID allowlist and broker mapping synchronized.
- Never put credentials, private keys, tokens, personal data, production hostnames, or unnecessary infrastructure details in the repository.
- Do not expose arbitrary environment paths as MCP arguments.
- Treat a change to the environment allowlist as a security-sensitive configuration change.
- Keep the broker socket local and permission-restricted.
- Prefer a dedicated broker account with the minimum Trac permissions required.

## Testing

Run the Python 3 adapter/CLI suites from the repository root:

```sh
python -m unittest tests.test_trac_mcp_protocol tests.test_trac_mcp_call
```

GitHub Actions also installs the package and checks both `trac-mcp` and
`trac-mcp-call` entry points on the supported Python matrix.

The broker fixture test is intentionally separate because it needs a disposable Trac environment that can be opened by the target Trac runtime. Run it with the same Python interpreter used by that Trac installation:

```sh
/path/to/trac-python tests/trac_broker_fixture_test.py /path/to/disposable/trac-environment
```

**Never point a fixture or destructive validation workflow at a production Trac environment.** Automated protocol tests, disposable-fixture testing, and production verification are different levels of evidence and should be reported separately.

## Trac 1.4.4 compatibility validation

The Trac 1.4.4 compatibility claim is based on integration testing, not only
unit/protocol tests. The broker was run using **Python 2.7.18 with Trac 1.4.4**
against disposable environments. The current expanded fixture covers:

- workflow-aware ticket creation, including custom creation actions;
- ticket workflow discovery and guarded action application, including dynamic
  action inputs such as resolution;
- ticket comments, guarded updates, direct deletion and batch
  create/update/delete with idempotent replay;
- wiki creation/list/search/history plus guarded deletion;
- bounded attachment upload/retrieval/listing plus guarded deletion;
- component/milestone/version creation/list/get/update/delete, including
  milestone dates and stale-snapshot rejection;
- enum listing plus guarded enum administration for mutable enum classes;
- broker health/server time, ticket-field metadata and recent wiki changes;
- denied-environment behavior;
- Unix-socket request reconstruction across multiple stream chunks and
  over-limit rejection.

Separate read-only smoke tests were then run against the actual staged Trac 1.4.4 environment. Environment allowlisting, `ticket_get`, `ticket_query`, and `wiki_list` passed. The staged environment was not modified by these tests.

Testing identified compatibility differences from the older Trac API and the broker was adjusted accordingly, notably for wiki-save arguments and ticket change timestamps. These fixes are part of the `v0.1.0` release candidate.

This evidence establishes compatibility with the tested **Trac 1.4.4/Python 2.7.18** combination. It should not be interpreted as a blanket compatibility claim for every Trac/Python/plugin/database combination. For a new deployment, use a disposable copy or test environment before production use.

## Trac 1.6 compatibility validation

Trac 1.6 compatibility was validated using **Python 3.9.2 with Trac 1.6** against a disposable copy of the upgraded staged environment. The copied environment retained the real upgraded database schema and content while allowing the unprivileged test account to meet Trac's SQLite write-permission requirement.

Validation includes the same expanded disposable broker fixture described
for Trac 1.4.4 above, run under **Trac 1.6 / Python 3**, plus:

- Python 3 adapter and local-CLI schema enforcement;
- rejection of unadvertised local-only/destructive tools through MCP;
- rejection of unknown/extra arguments, including attempts to override the
  broker operation name;
- explicit public environment allowlisting before the broker is contacted;
- installed-package smoke tests and verification of the 26 MCP-visible /
  12 local-only tool split;
- local wiki-file format detection, atomic TracWiki pull/push behavior, and
  symlink refusal.

Testing found two Python 3/Trac 1.6 compatibility issues in the broker: Python-2-specific text/byte handling (including attachment streams and octal syntax), and an older five-field wiki-history assumption. The broker now handles Python 2 and Python 3 text/byte types and accepts both four- and five-field wiki-history rows. The same fixture suite was rerun successfully with Trac 1.4.4/Python 2.7.18 after these changes.

Direct broker access to the staged Trac 1.6 environment itself was not forced because the test account intentionally lacks write access to its SQLite database directory and Trac refuses to open such an environment. This is a permissions boundary, not a broker API failure.

This evidence establishes compatibility with the tested **Trac 1.6/Python 3.9.2** combination. It is not a blanket guarantee for all plugin, database or Python combinations.

## Verifying a deployment

A safe deployment check should proceed from least invasive to more integrated:

1. confirm package installation and `trac-mcp` startup;
2. confirm broker service/socket health;
3. list the exposed environment IDs and verify the allowlist is exact;
4. perform read-only operations against a disposable or test environment;
5. test guarded writes only in a disposable/test environment;
6. verify denied environments and unsupported generic operations fail closed;
7. only then consider bounded read-only production verification.

Do not use production mutation as an installation test.

## Troubleshooting

### Adapter cannot connect to the socket

Check that `TRAC_MCP_SOCKET` is identical for adapter and broker, the broker is running, and the adapter account has permission to connect. Do not make the socket world-writable as a shortcut.

### Environment is reported as unknown or denied

Check both sides of the allowlist. The adapter needs the public ID and the broker needs a matching `id=/absolute/path` mapping. A failure for an unconfigured ID is expected security behaviour.

### Broker cannot import Trac

Run the configured broker interpreter directly and test `import trac`. Older Trac installations may use a dedicated Python environment. Use that environment rather than changing the server's global Python merely for this project.

### Permission denied on a Trac environment

Verify the broker service account and the target environment's intended ownership/permissions. Do not run the broker as root to make the error disappear.

If the broker is managed by systemd with `ProtectSystem=strict` and explicit `ReadWritePaths=`, remember that the service's mount namespace and writable-path bindings are established when the service starts. If an allowlisted Trac environment directory is later replaced, restored, atomically swapped or recreated at the same path, an already-running broker can retain a stale binding. A typical symptom is that reads still work while SQLite writes report a read-only database even though host-side ownership and modes look correct. Restart the broker service after such an environment replacement so systemd rebuilds the namespace and bindings; then re-check access. Do not weaken the sandbox or broaden database permissions as a workaround.

Also verify that the broker interpreter imports the same Trac runtime version that owns the target environment schema. A few API calls can appear to work across a Trac-library/schema mismatch while other operations fail. After upgrading Trac, run the broker with that target Trac runtime and repeat the broker fixture/integration validation before considering the deployment healthy.

### Python virtual environment cannot be created

Install the appropriate OS package providing Python's `venv`/`ensurepip` support. This is a host prerequisite, not a reason to develop as root.

## Upgrading

For a source deployment:

```sh
git fetch --tags
# Review the release notes before selecting a new release.
python -m pip install .
python -m unittest tests.test_trac_mcp_protocol tests.test_trac_mcp_call
```

Back up deployment configuration before changing it. Review `CHANGELOG.md` for configuration or compatibility changes. If the broker changes, validate it against a disposable Trac environment before replacing a production broker.

Run the adapter through the installed `trac-mcp` entry point. Do not copy `src/trac_mcp/server.py` out of the package as a standalone deployment file: the adapter intentionally shares validation code with the local CLI through the installed `trac_mcp` package. Older deployments that used a copied standalone adapter should migrate their service/gateway command to the installed entry point during upgrade, with a rollback copy of the previous command/configuration.

After changing the Trac runtime or upgrading the environments, test more than read-only discovery. Before reopening normal access, exercise a bounded write/read-back path in an approved test or maintenance target, then verify wiki history and attachment handling as well as ticket operations. Finally run the normal MCP client/adapter -> Unix socket -> broker -> Trac path end to end; direct broker calls alone do not prove that the deployed integration is healthy.

## Uninstalling

Remove the Python package using the same Python environment used to install it:

```sh
python -m pip uninstall trac-mcp
```

For a system deployment, separately disable/remove any broker service and its configuration/socket runtime files according to your operating system practices. Do not remove Trac environments or their data as part of uninstalling this MCP adapter.

## Security model and reporting

The constrained interface is intentional. The existing destructive operations are confined to the explicitly reviewed trusted-local `trac-mcp-call` tier. Requests to expose destructive/admin operations over MCP, or to add generic shell, SQL, arbitrary Trac/filesystem access or unrestricted `trac-admin`, require explicit security review rather than being treated as ordinary convenience features.

See `SECURITY.md` for vulnerability reporting and `PROVENANCE.md` for the initial source/provenance audit.

## Development and contributions

Read `CONTRIBUTING.md` before submitting changes. Keep commits focused, run the documented tests, and update documentation whenever requirements, installation, configuration, public behaviour, security boundaries, or compatibility change.

AI-assisted contributions are permitted subject to the disclosure, review, testing, confidentiality, and provenance requirements in `CONTRIBUTING.md`.

## Guidance for AI agents

AI agents working with this repository should follow the same instructions as human contributors and additionally:

1. Read this README, `AGENTS.md`, `SECURITY.md`, `CONTRIBUTING.md`, and relevant tests before modifying code.
2. Treat examples as placeholders, not evidence about a live deployment.
3. Never infer or invent production hostnames, paths, credentials, users, environment IDs, or service configuration.
4. Do routine source, Git, build, lint, and test work as the normal repository owner, not root.
5. Use privileged execution only for a narrowly scoped system operation that genuinely requires it and only when authorized.
6. Inspect Git status/history before changes and preserve unrelated work.
7. Run relevant automated tests and distinguish those results from integration/production validation.
8. Update this README when a change affects setup, requirements, configuration, operation, compatibility, or troubleshooting.
9. Before publishing/pushing, check tracked content **and commit metadata/history** for secrets, personal email addresses, private infrastructure details, or unintended operational data.
10. Do not weaken the project's bounded security model merely to make a test or deployment succeed.

`AGENTS.md` contains the concise repository rules intended for coding-agent discovery. This README remains the authoritative human-readable setup and operational guide.

## Repository layout

```text
src/trac_mcp/server.py         Python 3 MCP stdio adapter and MCP-visible registry
src/trac_mcp/call.py           trusted local one-shot CLI and local-only registry
src/trac_mcp/schema.py         shared bounded schema validator
legacy/trac_broker_py2.py      dual-runtime Trac compatibility broker (historical filename)
tests/                         protocol, CLI and cross-Trac broker fixture tests
docs/                          capability mapping and design/reference documentation
examples/                      generic environment/systemd examples
.github/workflows/             CI configuration
SECURITY.md                    vulnerability/security policy
CONTRIBUTING.md                contribution and AI-assistance policy
PROVENANCE.md                  source/provenance record
CHANGELOG.md                   release history
RELEASE_CHECKLIST.md           release-readiness record
```

## Known limitations

- The compatibility broker has been integration-tested with Trac 1.4.4 on Python 2.7.18 and Trac 1.6 on Python 3.9.2; other Trac/Python/plugin/database combinations still require their own validation.
- Client/gateway authentication is outside this repository's scope.
- The supplied systemd and environment files are examples and require local review.
- Production deployment cannot be proven solely by CI; validate against an appropriate disposable Trac environment first.

## Licence and authorship

Copyright (c) 2026 Kelly McLellan.

Licensed under the MIT License. See `LICENSE`.
